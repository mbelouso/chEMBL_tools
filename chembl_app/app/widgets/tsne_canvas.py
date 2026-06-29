import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy


class TSNECanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fig = Figure(figsize=(7, 5))
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._df = None
        self._annotation = None
        self._x_col = "tsne_x"
        self._y_col = "tsne_y"

        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)

    def set_figure(self, fig: Figure):
        self._fig = fig
        self._canvas.figure = fig
        fig.set_canvas(self._canvas)
        # Infer coordinate columns from the axis labels
        try:
            ax = fig.axes[0]
            xlabel = ax.get_xlabel().lower()
            if "umap" in xlabel:
                self._x_col, self._y_col = "umap_x", "umap_y"
            elif "pc" in xlabel:
                self._x_col, self._y_col = "pca_x", "pca_y"
            else:
                self._x_col, self._y_col = "tsne_x", "tsne_y"
        except (IndexError, AttributeError):
            pass
        self._toolbar.update()
        self._canvas.draw_idle()

    def set_dataframe(self, df: pd.DataFrame):
        self._df = df

    def _on_hover(self, event):
        if event.inaxes is None or self._df is None:
            return
        if self._x_col not in self._df.columns or self._y_col not in self._df.columns:
            return
        ax = event.inaxes
        if self._annotation:
            self._annotation.remove()
            self._annotation = None
        for _, row in self._df.iterrows():
            if abs(row[self._x_col] - event.xdata) < 1.5 and abs(row[self._y_col] - event.ydata) < 1.5:
                self._annotation = ax.annotate(
                    str(row.get("chembl_id", "")),
                    xy=(row[self._x_col], row[self._y_col]),
                    xytext=(10, 10),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.7),
                    fontsize=8,
                )
                self._canvas.draw_idle()
                break
