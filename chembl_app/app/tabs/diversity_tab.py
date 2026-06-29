import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel,
    QSpinBox, QDoubleSpinBox, QRadioButton, QCheckBox, QComboBox,
    QPushButton, QSplitter, QFileDialog, QTabWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.widgets.results_table import ResultsTable
from app.widgets.tsne_canvas import TSNECanvas
from app.widgets.activity_histogram import ActivityHistogramCanvas
from app.widgets.molecule_viewer import MoleculeViewer
from core.chemistry.clustering import ClusterParams
from core.chemistry.tsne import make_tsne_figure
from core.chemistry.projections import make_selection_overlay_figure


class DiversityTab(QWidget):
    cluster_requested = pyqtSignal(object)   # ClusterParams
    export_requested = pyqtSignal(str)       # output file path
    curation_changed = pyqtSignal(object)    # curated diversity DataFrame

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_df = pd.DataFrame()
        self._df_pre: pd.DataFrame = pd.DataFrame()
        self._df_diverse: pd.DataFrame = pd.DataFrame()
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self):
        root = QHBoxLayout(self)

        left = QWidget()
        left.setFixedWidth(360)
        left_layout = QVBoxLayout(left)
        left_layout.setAlignment(Qt.AlignTop)

        algo_box = QGroupBox("Clustering Algorithm")
        algo_layout = QVBoxLayout(algo_box)
        self._kmeans_rb = QRadioButton("K-means")
        self._gmm_rb = QRadioButton("GMM (Gaussian Mixture)")
        self._butina_rb = QRadioButton("Butina (Tanimoto threshold)")
        self._kmeans_rb.setChecked(True)
        algo_layout.addWidget(self._kmeans_rb)
        algo_layout.addWidget(self._gmm_rb)
        algo_layout.addWidget(self._butina_rb)

        cutoff_row = QHBoxLayout()
        self._butina_cutoff_spin = QDoubleSpinBox()
        self._butina_cutoff_spin.setRange(0.01, 1.0)
        self._butina_cutoff_spin.setSingleStep(0.05)
        self._butina_cutoff_spin.setValue(0.4)
        self._butina_cutoff_spin.setDecimals(2)
        self._butina_cutoff_label = QLabel("Distance cutoff (0–1)")
        cutoff_row.addWidget(self._butina_cutoff_label)
        cutoff_row.addWidget(self._butina_cutoff_spin)
        algo_layout.addLayout(cutoff_row)
        self._butina_cutoff_label.setVisible(False)
        self._butina_cutoff_spin.setVisible(False)

        left_layout.addWidget(algo_box)

        auto_box = QGroupBox("Class Estimation")
        auto_layout = QVBoxLayout(auto_box)
        self._auto_k_cb = QCheckBox("Estimate class count automatically")
        self._auto_k_cb.setChecked(True)
        auto_layout.addWidget(self._auto_k_cb)

        method_row = QHBoxLayout()
        self._auto_method_combo = QComboBox()
        self._auto_method_combo.addItem("Silhouette", userData="silhouette")
        self._auto_method_combo.addItem("Davies-Bouldin", userData="davies_bouldin")
        method_row.addWidget(QLabel("Method"))
        method_row.addWidget(self._auto_method_combo)
        auto_layout.addLayout(method_row)

        k_range_row = QHBoxLayout()
        self._kmin_spin = QSpinBox(); self._kmin_spin.setRange(2, 200); self._kmin_spin.setValue(4)
        self._kmax_spin = QSpinBox(); self._kmax_spin.setRange(2, 300); self._kmax_spin.setValue(40)
        k_range_row.addWidget(QLabel("k min")); k_range_row.addWidget(self._kmin_spin)
        k_range_row.addWidget(QLabel("k max")); k_range_row.addWidget(self._kmax_spin)
        auto_layout.addLayout(k_range_row)

        manual_row = QHBoxLayout()
        self._nc_spin = QSpinBox(); self._nc_spin.setRange(2, 200); self._nc_spin.setValue(20)
        manual_row.addWidget(QLabel("Manual classes")); manual_row.addWidget(self._nc_spin)
        auto_layout.addLayout(manual_row)

        self._auto_k_cb.toggled.connect(lambda checked: self._nc_spin.setEnabled(not checked))
        self._auto_k_cb.toggled.connect(self._auto_method_combo.setEnabled)
        self._nc_spin.setEnabled(False)
        left_layout.addWidget(auto_box)

        self._auto_box = auto_box  # keep ref for visibility toggling

        def _on_algo_changed():
            is_butina = self._butina_rb.isChecked()
            self._butina_cutoff_label.setVisible(is_butina)
            self._butina_cutoff_spin.setVisible(is_butina)
            self._auto_box.setVisible(not is_butina)

        self._kmeans_rb.toggled.connect(lambda _: _on_algo_changed())
        self._gmm_rb.toggled.connect(lambda _: _on_algo_changed())
        self._butina_rb.toggled.connect(lambda _: _on_algo_changed())

        mode_box = QGroupBox("Selection Strategy")
        mode_layout = QVBoxLayout(mode_box)
        self._random_rb = QRadioButton("Random near centroid")
        self._tight_rb = QRadioButton("Tightness representative")
        self._random_rb.setChecked(True)
        mode_layout.addWidget(self._random_rb)
        mode_layout.addWidget(self._tight_rb)

        random_row = QHBoxLayout()
        self._rpc_spin = QSpinBox(); self._rpc_spin.setRange(1, 100); self._rpc_spin.setValue(3)
        self._quantile_spin = QDoubleSpinBox(); self._quantile_spin.setRange(0.05, 1.0); self._quantile_spin.setSingleStep(0.05); self._quantile_spin.setValue(0.40)
        random_row.addWidget(QLabel("Per class")); random_row.addWidget(self._rpc_spin)
        random_row.addWidget(QLabel("Centroid q")); random_row.addWidget(self._quantile_spin)
        mode_layout.addLayout(random_row)

        seed_row = QHBoxLayout()
        self._seed_spin = QSpinBox(); self._seed_spin.setRange(0, 999999); self._seed_spin.setValue(42)
        seed_row.addWidget(QLabel("Random seed")); seed_row.addWidget(self._seed_spin)
        mode_layout.addLayout(seed_row)

        self._tightness_spin = QDoubleSpinBox()
        self._tightness_spin.setRange(0.0, 1.0)
        self._tightness_spin.setSingleStep(0.05)
        self._tightness_spin.setValue(0.30)
        self._tightness_spin.setDecimals(2)
        tight_row = QHBoxLayout()
        tight_row.addWidget(QLabel("Tightness quantile"))
        tight_row.addWidget(self._tightness_spin)
        mode_layout.addLayout(tight_row)
        left_layout.addWidget(mode_box)

        self._run_btn = QPushButton("Run Diversity")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._on_run)
        left_layout.addWidget(self._run_btn)

        self._export_btn = QPushButton("Export Filtered Results as CSV...")
        self._export_btn.setFixedHeight(36)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        left_layout.addWidget(self._export_btn)

        left_layout.addStretch()
        root.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self._summary_label = QLabel("No diversity run yet")
        self._summary_label.setStyleSheet("color: gray; font-style: italic;")
        right_layout.addWidget(self._summary_label)

        self._tabs = QTabWidget()

        results_view = QWidget()
        results_layout = QVBoxLayout(results_view)
        top_split = QSplitter(Qt.Horizontal)
        self.results_table = ResultsTable()
        self.molecule_viewer = MoleculeViewer()
        top_split.addWidget(self.results_table)
        top_split.addWidget(self.molecule_viewer)
        top_split.setSizes([650, 280])

        results_split = QSplitter(Qt.Horizontal)
        self.activity_histogram = ActivityHistogramCanvas()
        self.activity_histogram.curated_changed.connect(self._on_histogram_curated)
        results_split.addWidget(top_split)
        results_split.addWidget(self.activity_histogram)
        results_split.setSizes([720, 520])
        results_layout.addWidget(results_split)

        self.post_tsne_canvas = TSNECanvas()
        results_layout.addWidget(self.post_tsne_canvas)

        self.pre_tsne_canvas = TSNECanvas()

        overlay_widget = QWidget()
        overlay_layout = QVBoxLayout(overlay_widget)
        overlay_layout.setContentsMargins(4, 4, 4, 0)
        overlay_layout.setSpacing(2)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Selected color:"))
        self._overlay_cluster_rb = QRadioButton("Cluster (tab20)")
        self._overlay_single_rb = QRadioButton("Single (blue)")
        self._overlay_cluster_rb.setChecked(True)
        self._overlay_cluster_rb.toggled.connect(self._refresh_overlay)
        color_row.addWidget(self._overlay_cluster_rb)
        color_row.addWidget(self._overlay_single_rb)
        color_row.addStretch()
        overlay_layout.addLayout(color_row)

        self.overlay_canvas = TSNECanvas()
        overlay_layout.addWidget(self.overlay_canvas, stretch=1)

        self._tabs.addTab(results_view, "Post-filter")
        self._tabs.addTab(self.pre_tsne_canvas, "Pre-filter t-SNE")
        self._tabs.addTab(overlay_widget, "Selection Overlay")

        self.results_table.row_selected.connect(
            lambda smiles, cid: self.molecule_viewer.show_smiles(smiles, cid)
        )

        right_layout.addWidget(self._tabs)
        root.addWidget(right, stretch=1)

    def _on_run(self):
        if self._butina_rb.isChecked():
            algorithm = "butina"
        elif self._gmm_rb.isChecked():
            algorithm = "gmm"
        else:
            algorithm = "kmeans"

        k_min = min(self._kmin_spin.value(), self._kmax_spin.value())
        k_max = max(self._kmin_spin.value(), self._kmax_spin.value())
        params = ClusterParams(
            algorithm=algorithm,
            n_clusters=self._nc_spin.value(),
            auto_k=self._auto_k_cb.isChecked() if algorithm != "butina" else False,
            auto_k_method=str(self._auto_method_combo.currentData()),
            k_min=k_min,
            k_max=k_max,
            selection_mode="random_near_centroid" if self._random_rb.isChecked() else "tightness",
            random_per_cluster=self._rpc_spin.value(),
            centroid_quantile=self._quantile_spin.value(),
            random_seed=self._seed_spin.value(),
            tightness_quantile=self._tightness_spin.value(),
            butina_distance_cutoff=self._butina_cutoff_spin.value(),
        )
        self.cluster_requested.emit(params)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "diversity_filtered.csv", "CSV (*.csv)"
        )
        if path:
            self.export_requested.emit(path)

    def _on_histogram_curated(self, curated_df: pd.DataFrame):
        self.results_table.update_data(curated_df)
        self.post_tsne_canvas.set_dataframe(curated_df)
        self.molecule_viewer.clear()
        if not curated_df.empty and "cluster" in curated_df.columns:
            post_fig = make_tsne_figure(curated_df, color_col="cluster")
            self.post_tsne_canvas.set_figure(post_fig)
        self.curation_changed.emit(curated_df)

    def set_pre_filter_plot(self, df: pd.DataFrame, fig):
        self.pre_tsne_canvas.set_dataframe(df)
        self.pre_tsne_canvas.set_figure(fig)

    def set_overlay_plot(self, fig, df_pre: pd.DataFrame):
        # fig is ignored — we regenerate based on the current toggle state
        self._df_pre = df_pre

    def _refresh_overlay(self):
        if self._df_pre.empty or self._df_diverse.empty:
            return
        use_cluster = self._overlay_cluster_rb.isChecked()
        fig = make_selection_overlay_figure(
            self._df_pre, self._df_diverse,
            color_col="cluster" if use_cluster else None,
        )
        self.overlay_canvas.set_dataframe(self._df_pre)
        self.overlay_canvas.set_figure(fig)

    def set_summary(self, summary: dict):
        in_n = int(summary.get("input_count", 0))
        out_n = int(summary.get("output_count", 0))
        cls = int(summary.get("estimated_classes", 0))
        algorithm = str(summary.get("algorithm", "kmeans"))
        auto_method = str(summary.get("auto_k_method", "ensemble"))
        mode = str(summary.get("selection_mode", ""))
        pct = (100.0 * out_n / in_n) if in_n else 0.0
        method_label = "Butina" if algorithm == "butina" else auto_method
        self._summary_label.setText(
            f"Classes: {cls} ({method_label}) | Retained: {out_n}/{in_n} ({pct:.1f}%) | Mode: {mode}"
        )
        self._summary_label.setStyleSheet("color: #1f6f8b; font-weight: bold;")

    def set_busy(self, busy: bool):
        self._run_btn.setEnabled(not busy)
        self._run_btn.setText("Running..." if busy else "Run Diversity")

    def on_results_ready(self, df: pd.DataFrame):
        self._base_df = df.copy()
        self._df_diverse = df.copy()
        self.results_table.update_data(df)
        self.post_tsne_canvas.set_dataframe(df)
        self.activity_histogram.update_data(df)
        self.molecule_viewer.clear()
        self._export_btn.setEnabled(True)
        self._refresh_overlay()
