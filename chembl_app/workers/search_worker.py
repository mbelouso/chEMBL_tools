import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

from core.db.connection import get_connection
from core.db.queries import (
    query_by_properties,
    query_target_molregnos,
    query_target_molregnos_multi,
    query_all_activity_aggregates,
    query_export_details,
    nm_to_pchembl,
    pchembl_to_nm,
)
from core.chemistry.fingerprints import compute_fingerprints, add_purchasability
from core.chemistry.tsne import run_tsne, make_tsne_figure
from core.chemistry.projections import run_pca, make_projection_figure
from core.chemistry.clustering import ClusterParams, cluster, diversity_select


@dataclass
class SearchParams:
    mw_min: float = 500.0
    mw_max: float = 900.0
    logp_min: float = 3.0
    logp_max: float = 5.0
    target_names: list = field(default_factory=list)
    ic50_max_nm: Optional[float] = None
    ec50_max_nm: Optional[float] = None
    ki_max_nm: Optional[float] = None
    purchasable_only: bool = False


class SearchWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    results_ready = pyqtSignal(object, object, object)  # df, fps_array, tsne_coords
    plot_ready = pyqtSignal(object)                      # t-SNE Figure
    pca_plot_ready = pyqtSignal(object)                  # PCA Figure
    error = pyqtSignal(str)

    def __init__(self, db_path: str, params: SearchParams, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.params = params

    def run(self):
        try:
            p = self.params
            with get_connection(self.db_path) as conn:
                self.status.emit("Querying database (MW/LogP)…")
                self.progress.emit(5)
                df = query_by_properties(
                    conn,
                    (p.mw_min, p.mw_max),
                    (p.logp_min, p.logp_max),
                )
                if df.empty:
                    self.error.emit("No compounds found for the given MW/LogP range.")
                    return

                target_list = list(p.target_names)
                if target_list:
                    self.progress.emit(15)
                    if len(target_list) == 1:
                        self.status.emit(f"Filtering by target '{target_list[0]}'…")
                        tids = query_target_molregnos(conn, target_list[0])
                        df = df[df["molregno"].isin(tids)].reset_index(drop=True)
                        if df.empty:
                            self.error.emit("No compounds found for the specified target.")
                            return
                    else:
                        self.status.emit(f"Filtering by {len(target_list)} targets…")
                        per_target = query_target_molregnos_multi(conn, target_list)
                        all_tids = set().union(*per_target.values())
                        df = df[df["molregno"].isin(all_tids)].reset_index(drop=True)
                        if df.empty:
                            self.error.emit("No compounds found for any of the specified targets.")
                            return
                        df["matched_targets"] = df["molregno"].apply(
                            lambda m: ", ".join(t for t, s in per_target.items() if m in s)
                        )

                self.status.emit("Aggregating activity data (IC50/EC50/Ki)…")
                self.progress.emit(25)
                agg = query_all_activity_aggregates(conn, df["molregno"].tolist())
                if not agg.empty:
                    df = df.merge(agg, on="molregno", how="left")
                for act_type, col_pchembl, col_nm, max_nm in [
                    ("IC50", "best_ic50_pchembl", "best_ic50_nm", p.ic50_max_nm),
                    ("EC50", "best_ec50_pchembl", "best_ec50_nm", p.ec50_max_nm),
                    ("Ki",   "best_ki_pchembl",   "best_ki_nm",   p.ki_max_nm),
                ]:
                    if col_pchembl in df.columns:
                        df[col_nm] = df[col_pchembl].apply(
                            lambda v: round(pchembl_to_nm(v), 3) if pd.notna(v) else None
                        )
                    if max_nm is not None:
                        pchembl_min = nm_to_pchembl(max_nm)
                        df = df[df[col_pchembl].notna() & (df[col_pchembl] >= pchembl_min)].reset_index(drop=True)
                        if df.empty:
                            self.error.emit(f"No compounds pass the {act_type} filter.")
                            return

                self.status.emit("Collecting target metadata…")
                self.progress.emit(35)
                details = query_export_details(conn, df["molregno"].tolist())
                if not details.empty:
                    details = details.sort_values(["molregno", "best_pchembl"], ascending=[True, False])
                    primary_targets = details.drop_duplicates("molregno")[[
                        "molregno", "target_name", "target_chembl_id", "uniprot_accession",
                    ]].rename(columns={
                        "target_name": "target_name",
                        "target_chembl_id": "target_chembl_id",
                        "uniprot_accession": "target_uniprot",
                    })
                    df = df.merge(primary_targets, on="molregno", how="left")

            if p.purchasable_only:
                self.status.emit("Checking purchasability…")
                self.progress.emit(40)
                df = add_purchasability(df)
                df = df[df["purchasable"]].reset_index(drop=True)
                if df.empty:
                    self.error.emit("No purchasable compounds found.")
                    return

            self.status.emit("Generating Morgan fingerprints…")
            self.progress.emit(55)
            fps_array = compute_fingerprints(df)

            self.status.emit("Clustering (K-means)…")
            self.progress.emit(62)
            n_cl = min(20, len(df))
            cluster_params = ClusterParams(algorithm="kmeans", n_clusters=n_cl)
            labels, centers = cluster(fps_array, cluster_params)
            df["cluster"] = labels

            self.status.emit("Running PCA…")
            self.progress.emit(67)

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
