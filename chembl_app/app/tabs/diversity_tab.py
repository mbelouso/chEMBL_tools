import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel,
    QSlider, QSpinBox, QDoubleSpinBox, QRadioButton,
    QPushButton, QSplitter, QFileDialog, QMessageBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.widgets.results_table import ResultsTable
from app.widgets.tsne_canvas import TSNECanvas
from core.chemistry.clustering import ClusterParams


class DiversityTab(QWidget):
    cluster_requested = pyqtSignal(object)   # ClusterParams
    export_requested = pyqtSignal(str)        # output file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self):
        root = QHBoxLayout(self)

        # ── Left panel ────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setAlignment(Qt.AlignTop)

        # Algorithm
        algo_box = QGroupBox("Clustering Algorithm")
        algo_layout = QVBoxLayout(algo_box)
        self._kmeans_rb = QRadioButton("K-means")
        self._gmm_rb = QRadioButton("GMM (Gaussian Mixture)")
        self._kmeans_rb.setChecked(True)
        algo_layout.addWidget(self._kmeans_rb)
        algo_layout.addWidget(self._gmm_rb)
        left_layout.addWidget(algo_box)

        # N clusters
        nc_box = QGroupBox("Number of Clusters")
        nc_row = QHBoxLayout(nc_box)
        self._nc_slider = QSlider(Qt.Horizontal)
        self._nc_slider.setRange(5, 100)
        self._nc_slider.setValue(20)
        self._nc_spin = QSpinBox()
        self._nc_spin.setRange(5, 100)
        self._nc_spin.setValue(20)
        self._nc_slider.valueChanged.connect(self._nc_spin.setValue)
        self._nc_spin.valueChanged.connect(self._nc_slider.setValue)
        nc_row.addWidget(self._nc_slider, stretch=1)
        nc_row.addWidget(self._nc_spin)
        left_layout.addWidget(nc_box)

        # Tightness
        tight_box = QGroupBox("Tightness Quantile")
        tight_layout = QVBoxLayout(tight_box)
        tight_layout.addWidget(QLabel(
            "Fraction of tightest clusters from which\none representative is selected (0–1):"
        ))
        self._tightness_spin = QDoubleSpinBox()
        self._tightness_spin.setRange(0.0, 1.0)
        self._tightness_spin.setSingleStep(0.05)
        self._tightness_spin.setValue(0.30)
        self._tightness_spin.setDecimals(2)
        tight_layout.addWidget(self._tightness_spin)
        left_layout.addWidget(tight_box)

        # Run button
        self._run_btn = QPushButton("Run Clustering")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._on_run)
        left_layout.addWidget(self._run_btn)

        # Export button
        self._export_btn = QPushButton("Export Filtered Results as CSV…")
        self._export_btn.setFixedHeight(36)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        left_layout.addWidget(self._export_btn)

        left_layout.addStretch()
        root.addWidget(left)

        # ── Right panel ───────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        self.results_table = ResultsTable()
        self.tsne_canvas = TSNECanvas()
        splitter.addWidget(self.results_table)
        splitter.addWidget(self.tsne_canvas)
        splitter.setSizes([300, 400])
        root.addWidget(splitter, stretch=1)

    def _on_run(self):
        params = ClusterParams(
            algorithm="kmeans" if self._kmeans_rb.isChecked() else "gmm",
            n_clusters=self._nc_spin.value(),
            tightness_quantile=self._tightness_spin.value(),
        )
        self.cluster_requested.emit(params)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "diversity_filtered.csv", "CSV (*.csv)"
        )
        if path:
            self.export_requested.emit(path)

    def set_busy(self, busy: bool):
        self._run_btn.setEnabled(not busy)
        self._run_btn.setText("Running…" if busy else "Run Clustering")

    def on_results_ready(self, df: pd.DataFrame):
        self.results_table.update_data(df)
        self._export_btn.setEnabled(True)
