import numpy as np
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

from core.chemistry.clustering import (
    ClusterParams,
    cluster,
    diversity_select,
    estimate_n_clusters,
    random_select_near_centroid,
)
from core.chemistry.tsne import make_tsne_figure


class DiversityWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    results_ready = pyqtSignal(object)   # diverse DataFrame
    pre_plot_ready = pyqtSignal(object, object)  # pre-filter DataFrame, Figure
    plot_ready = pyqtSignal(object)      # Figure
    summary_ready = pyqtSignal(object)   # dict summary
    error = pyqtSignal(str)

    def __init__(
        self,
        df: pd.DataFrame,
        fps_array: np.ndarray,
        tsne_coords: np.ndarray,
        params: ClusterParams,
        parent=None,
    ):
        super().__init__(parent)
        self.df = df
        self.fps_array = fps_array
        self.tsne_coords = tsne_coords
        self.params = params

    def run(self):
        try:
            n_samples = int(self.fps_array.shape[0])
            if n_samples == 0:
                self.error.emit("No compounds available for diversity clustering.")
                return

            effective_params = ClusterParams(
                algorithm=self.params.algorithm,
                n_clusters=max(1, min(self.params.n_clusters, n_samples)),
                auto_k=self.params.auto_k,
                auto_k_method=self.params.auto_k_method,
                k_min=self.params.k_min,
                k_max=self.params.k_max,
                selection_mode=self.params.selection_mode,
                random_per_cluster=self.params.random_per_cluster,
                centroid_quantile=self.params.centroid_quantile,
                random_seed=self.params.random_seed,
                tightness_quantile=self.params.tightness_quantile,
            )

            if n_samples >= 3 and effective_params.auto_k:
                self.status.emit("Estimating number of classes…")
                self.progress.emit(12)
                effective_params.n_clusters = estimate_n_clusters(self.fps_array, effective_params)

            self.status.emit("Clustering…")
            self.progress.emit(20)
            if n_samples < 2:
                labels = np.zeros(n_samples, dtype=int)
                centers = self.fps_array[:1].copy()
            else:
                labels, centers = cluster(self.fps_array, effective_params)

            self.status.emit("Selecting diverse subset…")
            self.progress.emit(60)
            df_work = self.df.copy()
            df_work["cluster"] = labels
            df_work["tsne_x"] = self.tsne_coords[:, 0]
            df_work["tsne_y"] = self.tsne_coords[:, 1]

            pre_fig = make_tsne_figure(df_work, color_col="cluster")
            self.pre_plot_ready.emit(df_work.copy(), pre_fig)

            if effective_params.selection_mode == "random_near_centroid":
                df_diverse = random_select_near_centroid(df_work, self.fps_array, labels, centers, effective_params)
            else:
                df_diverse = diversity_select(df_work, self.fps_array, labels, centers, effective_params)

            self.status.emit("Rendering plot…")
            self.progress.emit(90)
            fig = make_tsne_figure(df_diverse, color_col="cluster")

            cluster_counts = (
                df_diverse["cluster"].value_counts().sort_index().to_dict()
                if "cluster" in df_diverse.columns else {}
            )
            self.summary_ready.emit({
                "input_count": len(df_work),
                "output_count": len(df_diverse),
                "estimated_classes": int(effective_params.n_clusters),
                "auto_k_method": effective_params.auto_k_method,
                "selection_mode": effective_params.selection_mode,
                "cluster_counts": cluster_counts,
            })

            self.progress.emit(100)
            self.results_ready.emit(df_diverse)
            self.plot_ready.emit(fig)
        except Exception as exc:
            self.error.emit(str(exc))
