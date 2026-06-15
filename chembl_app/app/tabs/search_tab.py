from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QLabel,
    QDoubleSpinBox, QLineEdit, QCheckBox, QPushButton,
    QSplitter, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.widgets.results_table import ResultsTable
from app.widgets.tsne_canvas import TSNECanvas
from workers.search_worker import SearchParams


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

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self._target_edit.setPlaceholderText("e.g. EGFR — leave blank for all")
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

    def set_busy(self, busy: bool):
        self._search_btn.setEnabled(not busy)
        self._search_btn.setText("Searching…" if busy else "Search")
