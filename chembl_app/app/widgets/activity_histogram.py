import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QSizePolicy, QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal


# pChEMBL column → display label
_ACTIVITY_COLS = [
    ("best_ic50_pchembl", "pIC50"),
    ("best_ec50_pchembl", "pEC50"),
    ("best_ki_pchembl",   "pKi"),
]

_SLIDER_STEPS = 1000   # slider resolution


class ActivityHistogramCanvas(QWidget):
    curated_changed = pyqtSignal(object)  # curated DataFrame

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = None
        self._current_col = None
        self._cutoff_val = None
        self._data_min = 0.0
        self._data_max = 10.0
        self._curated_df = pd.DataFrame()

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Top row: activity selector + stats + compound counts ───────
        top = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setFixedWidth(120)
        self._combo.currentIndexChanged.connect(self._on_activity_changed)
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("font-size: 11px; color: #333;")
        self._count_label = QLabel()
        self._count_label.setStyleSheet("font-size: 11px; color: #0b6d30; font-weight: bold;")
        top.addWidget(QLabel("Activity:"))
        top.addWidget(self._combo)
        top.addSpacing(12)
        top.addWidget(self._stats_label, stretch=1)
        top.addWidget(self._count_label)
        layout.addLayout(top)

        # ── Canvas ───────────────────────────────────────────────────────
        self._fig = Figure(figsize=(10.5, 3.8), tight_layout=True)
        self._ax_activity = self._fig.add_subplot(131)
        self._ax_mw = self._fig.add_subplot(132)
        self._ax_logp = self._fig.add_subplot(133)
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
        self._slider.setValue(0)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.setTickInterval(_SLIDER_STEPS // 10)
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setFixedWidth(72)
        self._reset_btn.clicked.connect(self._on_reset)
        self._above_label = QLabel()
        self._above_label.setStyleSheet("font-size: 11px;")
        bot.addWidget(self._cutoff_label)
        bot.addWidget(self._slider, stretch=1)
        bot.addWidget(self._reset_btn)
        bot.addSpacing(8)
        bot.addWidget(self._above_label)
        layout.addLayout(bot)

        self._show_empty()

    # ── Public API ───────────────────────────────────────────────────────

    def update_data(self, df: pd.DataFrame):
        self._df = df.copy()
        self._combo.blockSignals(True)
        self._combo.clear()
        for col, label in _ACTIVITY_COLS:
            if col in self._df.columns and self._df[col].notna().any():
                self._combo.addItem(label, userData=col)
        self._combo.blockSignals(False)

        if self._combo.count() == 0:
            self._curated_df = self._df.copy()
            self._draw_distributions(self._curated_df)
            self._update_count_label(len(self._df), len(self._curated_df))
            self.curated_changed.emit(self._curated_df)
            self._show_empty("No activity data available for these compounds.")
            return

        self._combo.setCurrentIndex(0)
        self._draw_for_current(reset_cutoff=True)

    def clear(self):
        self._df = None
        self._curated_df = pd.DataFrame()
        self._combo.clear()
        self._show_empty()

    # ── Private ──────────────────────────────────────────────────────────

    def _on_activity_changed(self, _index):
        self._draw_for_current(reset_cutoff=True)

    def _draw_for_current(self, reset_cutoff: bool = False):
        if self._df is None or self._combo.count() == 0:
            return
        col = self._combo.currentData()
        label = self._combo.currentText()
        self._current_col = col
        values = self._df[col].dropna().values
        self._draw_histogram(values, label, reset_cutoff=reset_cutoff)
        self._emit_curated()

    def _draw_histogram(self, values: np.ndarray, activity_name: str, reset_cutoff: bool = False):
        self._ax_activity.cla()

        if len(values) == 0:
            self._ax_activity.text(0.5, 0.5, "No data", transform=self._ax_activity.transAxes,
                          ha="center", va="center", color="gray")
            self._draw_distributions(pd.DataFrame())
            self._canvas.draw_idle()
            return

        self._data_min = float(values.min())
        self._data_max = float(values.max())

        if reset_cutoff or self._cutoff_val is None or not (self._data_min <= self._cutoff_val <= self._data_max):
            self._cutoff_val = self._data_min
        self._sync_slider_to_cutoff()

        n_bins = min(40, max(10, len(values) // 5))
        self._ax_activity.hist(values, bins=n_bins, color="steelblue", edgecolor="white",
                               linewidth=0.5, alpha=0.85)

        self._ax_activity.axvline(
            self._cutoff_val, color="#e63946", linewidth=1.8,
            linestyle="--", label=f"Cutoff {self._cutoff_val:.2f}",
        )

        self._ax_activity.set_xlabel(activity_name, fontsize=10)
        self._ax_activity.set_ylabel("Count", fontsize=10)
        self._ax_activity.set_title(f"{activity_name} distribution  (n={len(values)})", fontsize=11)
        self._ax_activity.tick_params(labelsize=9)
        self._fig.tight_layout()
        self._toolbar.update()

        self._update_stats(values, activity_name)

    def _on_slider_changed(self, slider_val: int):
        span = self._data_max - self._data_min
        if span == 0:
            return
        self._cutoff_val = self._data_min + (slider_val / _SLIDER_STEPS) * span
        if slider_val == 0:
            self._cutoff_label.setText("Cutoff: off")
        else:
            self._cutoff_label.setText(f"Cutoff: {self._cutoff_val:.2f}")
        self._draw_for_current(reset_cutoff=False)

    def _sync_slider_to_cutoff(self):
        span = self._data_max - self._data_min
        if span == 0:
            return
        frac = (self._cutoff_val - self._data_min) / span
        self._slider.blockSignals(True)
        self._slider.setValue(int(frac * _SLIDER_STEPS))
        self._slider.blockSignals(False)
        if self._slider.value() == 0:
            self._cutoff_label.setText("Cutoff: off")
        else:
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
        if self._slider.value() == 0:
            self._above_label.setText("No activity filter (showing all compounds)")
            return
        n_above = int((values >= self._cutoff_val).sum())
        pct = 100 * n_above / len(values) if len(values) else 0
        self._above_label.setText(f"≥ cutoff: {n_above} ({pct:.0f}%)")

    def _emit_curated(self):
        if self._df is None:
            return
        filter_active = bool(self._current_col) and (self._cutoff_val is not None) and (self._slider.value() > 0)
        if not filter_active:
            self._curated_df = self._df.copy()
        else:
            series = self._df[self._current_col]
            mask = series.notna() & (series >= self._cutoff_val)
            self._curated_df = self._df.loc[mask].copy()

        self._draw_distributions(self._curated_df)
        self._update_count_label(len(self._df), len(self._curated_df))
        self.curated_changed.emit(self._curated_df)

    def _draw_distributions(self, curated_df: pd.DataFrame):
        self._ax_mw.cla()
        self._ax_logp.cla()

        if curated_df.empty:
            self._ax_mw.text(0.5, 0.5, "No MW data", transform=self._ax_mw.transAxes,
                             ha="center", va="center", color="gray")
            self._ax_logp.text(0.5, 0.5, "No LogP data", transform=self._ax_logp.transAxes,
                               ha="center", va="center", color="gray")
            self._canvas.draw_idle()
            return

        if "molecular_weight" in curated_df.columns and curated_df["molecular_weight"].notna().any():
            mw_values = curated_df["molecular_weight"].dropna().values
            bins = min(40, max(8, len(mw_values) // 5))
            self._ax_mw.hist(mw_values, bins=bins, color="#3a86ff", edgecolor="white", linewidth=0.5)
            self._ax_mw.set_title("Molecular Weight", fontsize=10)
            self._ax_mw.set_xlabel("MW (Da)", fontsize=9)
            self._ax_mw.set_ylabel("Count", fontsize=9)
            self._ax_mw.tick_params(labelsize=8)
        else:
            self._ax_mw.text(0.5, 0.5, "No MW data", transform=self._ax_mw.transAxes,
                             ha="center", va="center", color="gray")

        if "alogp" in curated_df.columns and curated_df["alogp"].notna().any():
            logp_values = curated_df["alogp"].dropna().values
            bins = min(40, max(8, len(logp_values) // 5))
            self._ax_logp.hist(logp_values, bins=bins, color="#2a9d8f", edgecolor="white", linewidth=0.5)
            self._ax_logp.set_title("LogP", fontsize=10)
            self._ax_logp.set_xlabel("AlogP", fontsize=9)
            self._ax_logp.set_ylabel("Count", fontsize=9)
            self._ax_logp.tick_params(labelsize=8)
        else:
            self._ax_logp.text(0.5, 0.5, "No LogP data", transform=self._ax_logp.transAxes,
                               ha="center", va="center", color="gray")

        self._canvas.draw_idle()

    def _update_count_label(self, total_count: int, curated_count: int):
        pct = (100.0 * curated_count / total_count) if total_count else 0.0
        self._count_label.setText(f"Compounds: {curated_count}/{total_count} ({pct:.0f}%)")

    def _on_reset(self):
        if self._df is None or self._combo.count() == 0:
            return
        self._cutoff_val = self._data_min
        self._sync_slider_to_cutoff()
        self._draw_for_current(reset_cutoff=False)

    def _show_empty(self, msg: str = "Run a search to see activity distribution."):
        self._ax_activity.cla()
        self._ax_mw.cla()
        self._ax_logp.cla()
        self._ax_activity.text(0.5, 0.5, msg, transform=self._ax_activity.transAxes,
                               ha="center", va="center", color="gray", fontsize=10,
                               wrap=True)
        self._ax_activity.set_axis_off()
        self._ax_mw.text(0.5, 0.5, "Run search", transform=self._ax_mw.transAxes,
                         ha="center", va="center", color="gray", fontsize=9)
        self._ax_logp.text(0.5, 0.5, "Run search", transform=self._ax_logp.transAxes,
                           ha="center", va="center", color="gray", fontsize=9)
        self._ax_mw.set_axis_off()
        self._ax_logp.set_axis_off()
        self._canvas.draw_idle()
        self._stats_label.setText("")
        self._count_label.setText("")
        self._cutoff_label.setText("Cutoff: —")
        self._above_label.setText("")
