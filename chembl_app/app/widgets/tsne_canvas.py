import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import pyqtSignal


class TSNECanvas(QWidget):
    point_clicked = pyqtSignal(str)  # chembl_id of the clicked point

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fig = Figure(figsize=(7, 5))
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
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
        # A freshly-created Figure keeps whatever fixed size it was built with
        # (e.g. figsize=(7, 5)) instead of the canvas widget's actual current
        # size. The Agg renderer only allocates a buffer matching the figure's
        # size, so anything Qt paints beyond that buffer shows stale/garbage
        # image data instead of being cleared. Resize the figure to the
        # widget's current size before it's ever drawn.
        dpr = self._canvas.devicePixelRatioF() or 1
        dpi = fig.dpi
        w_in = max(self._canvas.width(), 1) * dpr / dpi
        h_in = max(self._canvas.height(), 1) * dpr / dpi
        fig.set_size_inches(w_in, h_in, forward=False)
        # canvas.callbacks is actually figure._canvas_callbacks, so a fresh
        # Figure means a fresh (empty) registry — reconnect every time.
        self._canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._canvas.mpl_connect("button_press_event", self._on_click)
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
        # Draw synchronously (not draw_idle) so the correctly-sized buffer is
        # in place immediately, with no dependency on the event loop's timing.
        self._canvas.draw()

    def set_dataframe(self, df: pd.DataFrame):
        self._df = df

    def _nearest_row(self, event, max_pixels: float):
        """Find the data row nearest to event, measured in screen pixels.

        Pixel distance (rather than a fixed data-unit threshold) is what
        makes this work consistently across t-SNE, PCA, and UMAP plots,
        whose coordinate ranges differ by orders of magnitude.
        """
        if event.inaxes is None or self._df is None or self._df.empty:
            return None
        if self._x_col not in self._df.columns or self._y_col not in self._df.columns:
            return None
        ax = event.inaxes
        points = ax.transData.transform(
            self._df[[self._x_col, self._y_col]].to_numpy()
        )
        dists = np.hypot(points[:, 0] - event.x, points[:, 1] - event.y)
        nearest = int(np.argmin(dists))
        if dists[nearest] > max_pixels:
            return None
        return self._df.iloc[nearest]

    def _on_hover(self, event):
        if self._annotation:
            self._annotation.remove()
            self._annotation = None
        row = self._nearest_row(event, max_pixels=12)
        if row is not None:
            self._annotation = event.inaxes.annotate(
                str(row.get("chembl_id", "")),
                xy=(row[self._x_col], row[self._y_col]),
                xytext=(10, 10),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.7),
                fontsize=8,
            )
        self._canvas.draw_idle()

    def _on_click(self, event):
        # Ignore clicks made while panning/zooming with the toolbar
        if event.button != 1 or self._toolbar.mode != "":
            return
        row = self._nearest_row(event, max_pixels=10)
        if row is None:
            return
        chembl_id = str(row.get("chembl_id", ""))
        if chembl_id:
            self.point_clicked.emit(chembl_id)
