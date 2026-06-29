import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel,
    QDoubleSpinBox, QLineEdit, QCheckBox, QPushButton,
    QSplitter, QSizePolicy, QCompleter, QTabWidget, QFileDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from app.widgets.results_table import ResultsTable
from app.widgets.tsne_canvas import TSNECanvas
from app.widgets.molecule_viewer import MoleculeViewer
from app.widgets.activity_histogram import ActivityHistogramCanvas
from core.chemistry.tsne import make_tsne_figure
from core.chemistry.projections import make_projection_figure
from workers.search_worker import SearchParams
from workers.target_names_worker import TargetNamesWorker


class _ActivityRow(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self._check = QCheckBox(label)
        self._spin = QDoubleSpinBox()
        self._spin.setRange(0.001, 1_000_000)
        self._spin.setValue(1000)
        self._spin.setSuffix(" nM")
        self._spin.setDecimals(1)
        self._spin.setEnabled(False)
        self._check.toggled.connect(self._spin.setEnabled)
        row.addWidget(self._check)
        row.addWidget(self._spin)

    def is_active(self) -> bool:
        return self._check.isChecked()

    def max_nm(self):
        return self._spin.value() if self._check.isChecked() else None


class SearchTab(QWidget):
    search_requested = pyqtSignal(object)   # SearchParams
    export_requested = pyqtSignal(str)      # output file path
    curation_changed = pyqtSignal(object)   # curated DataFrame

    def __init__(self, parent=None):
        super().__init__(parent)
        self._names_worker: TargetNamesWorker = None
        self._names_loaded = False
        self._base_df = pd.DataFrame()
        self._target_completer: QCompleter = None
        self._target_prefix: str = ""
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)

        # ── Left panel ────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setAlignment(Qt.AlignTop)

        # MW
        mw_box = QGroupBox("Molecular Weight (Da)")
        mw_row = QHBoxLayout(mw_box)
        self._mw_min = QDoubleSpinBox(); self._mw_min.setRange(0, 2000); self._mw_min.setValue(500)
        self._mw_max = QDoubleSpinBox(); self._mw_max.setRange(0, 2000); self._mw_max.setValue(900)
        mw_row.addWidget(QLabel("Min")); mw_row.addWidget(self._mw_min)
        mw_row.addWidget(QLabel("Max")); mw_row.addWidget(self._mw_max)
        left_layout.addWidget(mw_box)

        # LogP
        logp_box = QGroupBox("LogP")
        logp_row = QHBoxLayout(logp_box)
        self._logp_min = QDoubleSpinBox(); self._logp_min.setRange(-10, 20); self._logp_min.setValue(3); self._logp_min.setDecimals(1)
        self._logp_max = QDoubleSpinBox(); self._logp_max.setRange(-10, 20); self._logp_max.setValue(5); self._logp_max.setDecimals(1)
        logp_row.addWidget(QLabel("Min")); logp_row.addWidget(self._logp_min)
        logp_row.addWidget(QLabel("Max")); logp_row.addWidget(self._logp_max)
        left_layout.addWidget(logp_box)

        # Target
        tgt_box = QGroupBox("Target")
        tgt_layout = QVBoxLayout(tgt_box)
        self._target_edit = QLineEdit()
        self._target_edit.setPlaceholderText("e.g. EGFR, BRAF — comma-separated, leave blank for all")
        tgt_layout.addWidget(self._target_edit)
        left_layout.addWidget(tgt_box)

        # Activity filters
        act_box = QGroupBox("Activity Filters (max value)")
        act_layout = QVBoxLayout(act_box)
        self._ic50_row = _ActivityRow("IC50 ≤")
        self._ec50_row = _ActivityRow("EC50 ≤")
        self._ki_row   = _ActivityRow("Ki ≤")
        act_layout.addWidget(self._ic50_row)
        act_layout.addWidget(self._ec50_row)
        act_layout.addWidget(self._ki_row)
        left_layout.addWidget(act_box)

        # Purchasable
        self._purchasable_cb = QCheckBox("Purchasable compounds only")
        left_layout.addWidget(self._purchasable_cb)

        # Search button
        self._search_btn = QPushButton("Search")
        self._search_btn.setFixedHeight(36)
        self._search_btn.clicked.connect(self._on_search)
        left_layout.addWidget(self._search_btn)

        self._export_btn = QPushButton("Export Search Results as CSV…")
        self._export_btn.setFixedHeight(36)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        left_layout.addWidget(self._export_btn)

        left_layout.addStretch()
        root.addWidget(left)

        # ── Right panel ───────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # Count label
        self._count_label = QLabel("No results yet")
        self._count_label.setStyleSheet("color: gray; font-style: italic;")
        right_layout.addWidget(self._count_label)

        # Vertical splitter: table+viewer on top, t-SNE on bottom
        outer_splitter = QSplitter(Qt.Vertical)

        # Top: table on left, molecule viewer on right
        top_splitter = QSplitter(Qt.Horizontal)
        self.results_table = ResultsTable()
        self.molecule_viewer = MoleculeViewer()
        top_splitter.addWidget(self.results_table)
        top_splitter.addWidget(self.molecule_viewer)
        top_splitter.setSizes([600, 280])

        # Projection tabs: t-SNE / PCA
        self._projection_tabs = QTabWidget()
        self._projection_tabs.setTabPosition(QTabWidget.South)
        self.tsne_canvas = TSNECanvas()
        self.pca_canvas  = TSNECanvas()
        self.activity_histogram = ActivityHistogramCanvas()
        self._projection_tabs.addTab(self.tsne_canvas,       "t-SNE")
        self._projection_tabs.addTab(self.pca_canvas,        "PCA")
        self._projection_tabs.addTab(self.activity_histogram, "Distributions")
        self.activity_histogram.curated_changed.connect(self._on_curated_changed)

        outer_splitter.addWidget(top_splitter)
        outer_splitter.addWidget(self._projection_tabs)
        outer_splitter.setSizes([320, 380])

        right_layout.addWidget(outer_splitter)
        root.addWidget(right, stretch=1)

        # Wire molecule preview
        self.results_table.row_selected.connect(
            lambda smiles, cid: self.molecule_viewer.show_smiles(smiles, cid)
        )

    def set_db_path(self, db_path: str):
        if self._names_loaded:
            return  # already done
        if self._names_worker and self._names_worker.isRunning():
            return  # already loading
        self._target_edit.setPlaceholderText("Loading targets…")
        self._names_worker = TargetNamesWorker(db_path)
        self._names_worker.names_ready.connect(self._on_target_names_ready)
        self._names_worker.error.connect(
            lambda _: self._target_edit.setPlaceholderText("e.g. EGFR, BRAF — comma-separated, leave blank for all")
        )
        self._names_worker.start()

    def _on_target_names_ready(self, names: list):
        self._names_loaded = True
        self._target_edit.setPlaceholderText("e.g. EGFR, BRAF — comma-separated, leave blank for all")

        self._target_completer = QCompleter(names, self)
        self._target_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._target_completer.setFilterMode(Qt.MatchContains)
        self._target_completer.setMaxVisibleItems(12)
        self._target_completer.setCompletionMode(QCompleter.PopupCompletion)
        # Use setWidget instead of setCompleter so we control multi-token insertion
        self._target_completer.setWidget(self._target_edit)

        self._target_edit.textEdited.connect(self._on_target_text_edited)
        self._target_completer.activated.connect(self._on_target_completion)

    def _on_target_text_edited(self, text: str):
        parts = text.split(",")
        self._target_prefix = ",".join(parts[:-1])
        last = parts[-1].lstrip()
        self._target_completer.setCompletionPrefix(last)
        if last:
            self._target_completer.complete()
        else:
            self._target_completer.popup().hide()

    def _on_target_completion(self, completion: str):
        if self._target_prefix:
            new_text = self._target_prefix + ", " + completion
        else:
            new_text = completion
        self._target_edit.setText(new_text)
        self._target_edit.setCursorPosition(len(new_text))

    def _on_search(self):
        params = SearchParams(
            mw_min=self._mw_min.value(),
            mw_max=self._mw_max.value(),
            logp_min=self._logp_min.value(),
            logp_max=self._logp_max.value(),
            target_text=self._target_edit.text().strip(),
            ic50_max_nm=self._ic50_row.max_nm(),
            ec50_max_nm=self._ec50_row.max_nm(),
            ki_max_nm=self._ki_row.max_nm(),
            purchasable_only=self._purchasable_cb.isChecked(),
        )
        self.search_requested.emit(params)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Search Results", "search_results.csv", "CSV (*.csv)"
        )
        if path:
            self.export_requested.emit(path)

    def _on_curated_changed(self, curated_df: pd.DataFrame):
        self.results_table.update_data(curated_df)
        self.tsne_canvas.set_dataframe(curated_df)
        self.pca_canvas.set_dataframe(curated_df)
        self.set_result_count(len(curated_df))

        if not curated_df.empty and "cluster" in curated_df.columns:
            tsne_fig = make_tsne_figure(curated_df, color_col="cluster")
            self.tsne_canvas.set_figure(tsne_fig)

            if "pca_x" in curated_df.columns and "pca_y" in curated_df.columns:
                pca_fig = make_projection_figure(
                    curated_df, "pca_x", "pca_y", "PC 1", "PC 2",
                    f"PCA — {len(curated_df)} compounds", color_col="cluster",
                )
                self.pca_canvas.set_figure(pca_fig)

        self.curation_changed.emit(curated_df)

    def set_search_results(self, df: pd.DataFrame):
        self._base_df = df.copy()
        self.results_table.update_data(df)
        self.tsne_canvas.set_dataframe(df)
        self.pca_canvas.set_dataframe(df)
        self.activity_histogram.update_data(df)
        self.set_result_count(len(df))
        self._export_btn.setEnabled(True)

    def set_result_count(self, count: int):
        if count == 0:
            self._count_label.setText("No compounds found.")
            self._count_label.setStyleSheet("color: gray; font-style: italic;")
        else:
            self._count_label.setText(f"{count} compound{'s' if count != 1 else ''} found")
            self._count_label.setStyleSheet("color: #2a7a2a; font-weight: bold;")
        self.molecule_viewer.clear()

    def set_busy(self, busy: bool):
        self._search_btn.setEnabled(not busy)
        self._search_btn.setText("Searching…" if busy else "Search")
        self._export_btn.setEnabled((not busy) and (not self._base_df.empty))
        if busy:
            self._count_label.setText("Searching…")
            self._count_label.setStyleSheet("color: gray; font-style: italic;")
            self.activity_histogram.clear()
