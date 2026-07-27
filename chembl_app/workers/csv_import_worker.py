import pandas as pd
from rdkit import Chem
from PyQt5.QtCore import QThread, pyqtSignal

from core.chemistry.fingerprints import compute_fingerprints
from core.chemistry.tsne import run_tsne, make_tsne_figure
from core.chemistry.projections import run_pca, make_projection_figure
from core.chemistry.clustering import ClusterParams, cluster

_SMILES_ALIASES = {"canonical_smiles", "smiles"}
_ID_ALIASES = {"chembl_id", "compound_id", "molecule_chembl_id", "id"}


class CSVImportWorker(QThread):
    """Loads a presearched CSV and runs the same fingerprint/cluster/
    projection pipeline as SearchWorker, so results feed into the rest of
    the app identically to a fresh DB search."""

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    results_ready = pyqtSignal(object, object, object)  # df, fps_array, tsne_coords
    plot_ready = pyqtSignal(object)                      # t-SNE Figure
    pca_plot_ready = pyqtSignal(object)                  # PCA Figure
    error = pyqtSignal(str)

    def __init__(self, csv_path: str, parent=None):
        super().__init__(parent)
        self.csv_path = csv_path

    def run(self):
        try:
            self.status.emit("Reading CSV…")
            self.progress.emit(5)
            df = pd.read_csv(self.csv_path)

            rename = {}
            for col in df.columns:
                lc = col.strip().lower()
                if lc in _SMILES_ALIASES and "canonical_smiles" not in df.columns:
                    rename[col] = "canonical_smiles"
                elif lc in _ID_ALIASES and "chembl_id" not in df.columns:
                    rename[col] = "chembl_id"
            if rename:
                df = df.rename(columns=rename)

            if "canonical_smiles" not in df.columns:
                self.error.emit(
                    "No SMILES column found in the CSV. Expected a column "
                    "named 'canonical_smiles' or 'smiles'."
                )
                return

            df = df.reset_index(drop=True)
            if "chembl_id" not in df.columns:
                df["chembl_id"] = [f"IMPORT_{i + 1}" for i in range(len(df))]

            self.status.emit("Validating structures…")
            self.progress.emit(15)
            valid = df["canonical_smiles"].apply(
                lambda s: pd.notna(s) and Chem.MolFromSmiles(str(s)) is not None
            )
            n_bad = int((~valid).sum())
            df = df[valid].reset_index(drop=True)
            if df.empty:
                self.error.emit("No valid SMILES found in the CSV.")
                return
            if n_bad:
                self.status.emit(f"Skipped {n_bad} row(s) with unparseable SMILES…")

            self.status.emit("Generating Morgan fingerprints…")
            self.progress.emit(35)
            fps_array = compute_fingerprints(df)

            self.status.emit("Clustering (K-means)…")
            self.progress.emit(55)
            n_cl = min(20, len(df))
            labels, centers = cluster(fps_array, ClusterParams(algorithm="kmeans", n_clusters=n_cl))
            df["cluster"] = labels

            self.status.emit("Running PCA…")
            self.progress.emit(65)
            pca_coords = run_pca(fps_array)
            df["pca_x"] = pca_coords[:, 0]
            df["pca_y"] = pca_coords[:, 1]
            pca_fig = make_projection_figure(
                df, "pca_x", "pca_y", "PC 1", "PC 2",
                f"PCA — {len(df)} compounds", color_col="cluster",
            )
            self.pca_plot_ready.emit(pca_fig)
            self.progress.emit(75)

            self.status.emit("Running t-SNE…")
            tsne_coords = run_tsne(fps_array)
            df["tsne_x"] = tsne_coords[:, 0]
            df["tsne_y"] = tsne_coords[:, 1]
            tsne_fig = make_tsne_figure(df, color_col="cluster")
            self.plot_ready.emit(tsne_fig)
            self.progress.emit(92)

            self.progress.emit(100)
            self.results_ready.emit(df, fps_array, tsne_coords)

        except Exception as exc:
            self.error.emit(str(exc))
