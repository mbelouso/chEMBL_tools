import numpy as np
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

from core.chemistry.clustering import ClusterParams, cluster, diversity_select
from core.chemistry.tsne import make_tsne_figure


class DiversityWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    results_ready = pyqtSignal(object)   # diverse DataFrame
    plot_ready = pyqtSignal(object)      # Figure
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
            self.status.emit("Clustering…")
            self.progress.emit(20)
            labels, centers = cluster(self.fps_array, self.params)

            self.status.emit("Selecting diverse subset…")
            self.progress.emit(60)
            df_work = self.df.copy()
            df_work["tsne_x"] = self.tsne_coords[:, 0]
            df_work["tsne_y"] = self.tsne_coords[:, 1]
            df_diverse = diversity_select(df_work, self.fps_array, labels, centers, self.params)

            self.status.emit("Rendering plot…")
            self.progress.emit(90)
            fig = make_tsne_figure(df_diverse, color_col="cluster")

            self.progress.emit(100)
            self.results_ready.emit(df_diverse)
            self.plot_ready.emit(fig)
        except Exception as exc:
            self.error.emit(str(exc))
