import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QSizePolicy,
)
from PyQt5.QtCore import Qt


# pChEMBL column → display label
_ACTIVITY_COLS = [
    ("best_ic50_pchembl", "pIC50"),
    ("best_ec50_pchembl", "pEC50"),
    ("best_ki_pchembl",   "pKi"),
]

_SLIDER_STEPS = 1000   # slider resolution


class ActivityHistogramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = None
        self._current_col = None
        self._cutoff_line = None
        self._cutoff_val = None
        self._data_min = 0.0
        self._data_max = 10.0

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Top row: activity selector + stats ──────────────────────────
        top = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setFixedWidth(100)
        self._combo.currentIndexChanged.connect(self._on_activity_changed)
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("font-size: 11px; color: #333;")
        top.addWidget(QLabel("Activity:"))
        top.addWidget(self._combo)
        top.addSpacing(12)
        top.addWidget(self._stats_label, stretch=1)
        layout.addLayout(top)

        # ── Canvas ───────────────────────────────────────────────────────
        self._fig = Figure(figsize=(6, 3.5), tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)

        # ── Bottom row: cutoff slider ────────────────────────────────────
        bot = QHBoxLayout()
        self._cutoff_label = QLabel("Cutoff: —")
        self._cutoff_label.setFixedWidth(110)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, _SLIDER_STEPS)
        self._slider.setValue(_SLIDER_STEPS // 2)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.setTickInterval(_SLIDER_STEPS // 10)
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._above_label = QLabel()
        self._above_label.setStyleSheet("font-size: 11px;")
        bot.addWidget(self._cutoff_label)
        bot.addWidget(self._slider, stretch=1)
        bot.addSpacing(8)
        bot.addWidget(self._above_label)
        layout.addLayout(bot)

        self._show_empty()

    # ── Public API ───────────────────────────────────────────────────────

    def update_data(self, df: pd.DataFrame):
        self._df = df
        self._combo.blockSignals(True)
        self._combo.clear()
        for col, label in _ACTIVITY_COLS:
            if col in df.columns and df[col].notna().any():
                self._combo.addItem(label, userData=col)
        self._combo.blockSignals(False)

        if self._combo.count() == 0:
            self._show_empty("No activity data available for these compounds.")
            return

        self._combo.setCurrentIndex(0)
        self._draw_for_current()

    def clear(self):
        self._df = None
        self._combo.clear()
        self._show_empty()

    # ── Private ──────────────────────────────────────────────────────────

    def _on_activity_changed(self, _index):
        self._draw_for_current()

    def _draw_for_current(self):
        if self._df is None or self._combo.count() == 0:
            return
        col = self._combo.currentData()
        label = self._combo.currentText()
        self._current_col = col
        values = self._df[col].dropna().values
        self._draw_histogram(values, label)

    def _draw_histogram(self, values: np.ndarray, activity_name: str):
        self._ax.cla()

        if len(values) == 0:
            self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes,
                          ha="center", va="center", color="gray")
            self._canvas.draw_idle()
            return

        self._data_min = float(values.min())
        self._data_max = float(values.max())

        # Choose initial cutoff at median if not yet set or out of range
        median = float(np.median(values))
        if self._cutoff_val is None or not (self._data_min <= self._cutoff_val <= self._data_max):
            self._cutoff_val = median
        self._sync_slider_to_cutoff()

        n_bins = min(40, max(10, len(values) // 5))
        self._ax.hist(values, bins=n_bins, color="steelblue", edgecolor="white",
                      linewidth=0.5, alpha=0.85)

        self._cutoff_line = self._ax.axvline(
            self._cutoff_val, color="#e63946", linewidth=1.8,
            linestyle="--", label=f"Cutoff {self._cutoff_val:.2f}",
        )

        self._ax.set_xlabel(activity_name, fontsize=10)
        self._ax.set_ylabel("Count", fontsize=10)
        self._ax.set_title(f"{activity_name} distribution  (n={len(values)})", fontsize=11)
        self._ax.tick_params(labelsize=9)
        self._fig.tight_layout()
        self._toolbar.update()
        self._canvas.draw_idle()

        self._update_stats(values, activity_name)

    def _on_slider_changed(self, slider_val: int):
        span = self._data_max - self._data_min
        if span == 0:
            return
        self._cutoff_val = self._data_min + (slider_val / _SLIDER_STEPS) * span
        self._cutoff_label.setText(f"Cutoff: {self._cutoff_val:.2f}")

        if self._cutoff_line is not None:
            self._cutoff_line.set_xdata([self._cutoff_val, self._cutoff_val])
            self._canvas.draw_idle()

        if self._df is not None and self._current_col:
            values = self._df[self._current_col].dropna().values
            self._update_above_label(values)

    def _sync_slider_to_cutoff(self):
        span = self._data_max - self._data_min
        if span == 0:
            return
        frac = (self._cutoff_val - self._data_min) / span
        self._slider.blockSignals(True)
        self._slider.setValue(int(frac * _SLIDER_STEPS))
        self._slider.blockSignals(False)
        self._cutoff_label.setText(f"Cutoff: {self._cutoff_val:.2f}")

    def _update_stats(self, values: np.ndarray, activity_name: str):
        if len(values) == 0:
            self._stats_label.setText("")
            self._above_label.setText("")
            return
        median = np.median(values)
        lo, hi = values.min(), values.max()
        self._stats_label.setText(
            f"n={len(values)}  |  median={median:.2f}  |  "
            f"range {lo:.2f} – {hi:.2f}"
        )
        self._update_above_label(values)

    def _update_above_label(self, values: np.ndarray):
        if self._cutoff_val is None:
            return
        n_above = int((values >= self._cutoff_val).sum())
        pct = 100 * n_above / len(values) if len(values) else 0
        self._above_label.setText(f"≥ cutoff: {n_above} ({pct:.0f}%)")

    def _show_empty(self, msg: str = "Run a search to see activity distribution."):
        self._ax.cla()
        self._ax.text(0.5, 0.5, msg, transform=self._ax.transAxes,
                      ha="center", va="center", color="gray", fontsize=10,
                      wrap=True)
        self._ax.set_axis_off()
        self._canvas.draw_idle()
        self._stats_label.setText("")
        self._cutoff_label.setText("Cutoff: —")
        self._above_label.setText("")
