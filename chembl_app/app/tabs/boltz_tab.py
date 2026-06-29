import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QPlainTextEdit, QRadioButton,
    QComboBox, QSpinBox, QFileDialog, QMessageBox, QProgressBar,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from core.io.yaml_generator import YAMLParams

_SETTINGS_ORG = "chEMBL_tools"
_SETTINGS_APP = "BoltzTab"
_KEY_OUTDIR   = "yaml/last_output_dir"


class BoltzTab(QWidget):
    yaml_requested = pyqtSignal(object)   # YAMLParams + df embedded via main_window
    msa_query_requested = pyqtSignal(str, str)   # sequence, output_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._build_ui()
        saved_dir = self._settings.value(_KEY_OUTDIR, "")
        if saved_dir:
            self._outdir_edit.setText(saved_dir)
        self.setEnabled(False)

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Dataset selector ─────────────────────────────────────────
        src_box = QGroupBox("Compound Set to Export")
        src_row = QHBoxLayout(src_box)
        src_row.addWidget(QLabel("Use:"))
        self._src_combo = QComboBox()
        self._src_combo.addItems(["Search results", "Diversity-filtered results"])
        src_row.addWidget(self._src_combo)
        src_row.addStretch()
        root.addWidget(src_box)

        # ── Protein ───────────────────────────────────────────────────
        prot_box = QGroupBox("Protein Sequence")
        prot_layout = QVBoxLayout(prot_box)
        self._seq_edit = QPlainTextEdit()
        self._seq_edit.setPlaceholderText("Paste amino acid sequence here, or load FASTA…")
        self._seq_edit.setMaximumHeight(120)
        prot_layout.addWidget(self._seq_edit)
        fasta_row = QHBoxLayout()
        self._fasta_path_lbl = QLabel("No file loaded")
        fasta_btn = QPushButton("Load FASTA…")
        fasta_btn.clicked.connect(self._load_fasta)
        fasta_row.addWidget(fasta_btn)
        fasta_row.addWidget(self._fasta_path_lbl, stretch=1)
        prot_layout.addLayout(fasta_row)
        root.addWidget(prot_box)

        # ── MSA ───────────────────────────────────────────────────────
        msa_box = QGroupBox("Multiple Sequence Alignment (MSA)")
        msa_layout = QVBoxLayout(msa_box)
        msa_file_row = QHBoxLayout()
        self._msa_edit = QLineEdit()
        self._msa_edit.setPlaceholderText("Path to .a3m file")
        browse_msa = QPushButton("Browse…")
        browse_msa.clicked.connect(self._browse_msa)
        msa_file_row.addWidget(self._msa_edit, stretch=1)
        msa_file_row.addWidget(browse_msa)
        msa_layout.addLayout(msa_file_row)

        msa_btn_row = QHBoxLayout()
        self._colabfold_btn = QPushButton("Query ColabFold (generate MSA)")
        self._colabfold_btn.clicked.connect(self._query_colabfold)
        msa_btn_row.addWidget(self._colabfold_btn)
        msa_layout.addLayout(msa_btn_row)

        self._msa_progress = QProgressBar()
        self._msa_progress.setVisible(False)
        msa_layout.addWidget(self._msa_progress)
        self._msa_status_lbl = QLabel("")
        msa_layout.addWidget(self._msa_status_lbl)
        root.addWidget(msa_box)

        # ── YAML options ──────────────────────────────────────────────
        yaml_box = QGroupBox("YAML Generation Options")
        yaml_layout = QVBoxLayout(yaml_box)

        mode_row = QHBoxLayout()
        self._affinity_rb = QRadioButton("Affinity mode")
        self._template_rb = QRadioButton("Template mode")
        self._affinity_rb.setChecked(True)
        self._affinity_rb.toggled.connect(self._on_mode_toggle)
        mode_row.addWidget(self._affinity_rb)
        mode_row.addWidget(self._template_rb)
        mode_row.addStretch()
        yaml_layout.addLayout(mode_row)

        self._cif_row = QWidget()
        cif_row_layout = QHBoxLayout(self._cif_row)
        cif_row_layout.setContentsMargins(0, 0, 0, 0)
        self._cif_edit = QLineEdit()
        self._cif_edit.setPlaceholderText("Path to template .cif file")
        cif_browse = QPushButton("Browse…")
        cif_browse.clicked.connect(self._browse_cif)
        cif_row_layout.addWidget(QLabel("Template CIF:"))
        cif_row_layout.addWidget(self._cif_edit, stretch=1)
        cif_row_layout.addWidget(cif_browse)
        self._cif_row.setVisible(False)
        yaml_layout.addWidget(self._cif_row)

        out_row = QHBoxLayout()
        self._outdir_edit = QLineEdit()
        self._outdir_edit.setPlaceholderText("Output directory for YAML files")
        browse_out = QPushButton("Browse…")
        browse_out.clicked.connect(self._browse_outdir)
        out_row.addWidget(QLabel("Output dir:"))
        out_row.addWidget(self._outdir_edit, stretch=1)
        out_row.addWidget(browse_out)
        yaml_layout.addLayout(out_row)

        ndirs_row = QHBoxLayout()
        self._ndirs_spin = QSpinBox()
        self._ndirs_spin.setRange(1, 8)
        self._ndirs_spin.setValue(4)
        ndirs_row.addWidget(QLabel("Number of subdirectories:"))
        ndirs_row.addWidget(self._ndirs_spin)
        ndirs_row.addStretch()
        yaml_layout.addLayout(ndirs_row)

        root.addWidget(yaml_box)

        # ── Generate button + progress ────────────────────────────────
        self._gen_btn = QPushButton("Generate YAML Files")
        self._gen_btn.setFixedHeight(40)
        self._gen_btn.clicked.connect(self._on_generate)
        root.addWidget(self._gen_btn)

        self._yaml_progress = QProgressBar()
        self._yaml_progress.setVisible(False)
        root.addWidget(self._yaml_progress)

        self._yaml_status_lbl = QLabel("")
        root.addWidget(self._yaml_status_lbl)
        root.addStretch()

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_mode_toggle(self, affinity: bool):
        self._cif_row.setVisible(not affinity)

    def _load_fasta(self):
        from core.io.fasta import read_fasta
        path, _ = QFileDialog.getOpenFileName(
            self, "Open FASTA", "", "FASTA (*.fasta *.fa *.txt);;All files (*)"
        )
        if not path:
            return
        try:
            seq = read_fasta(path)
            self._seq_edit.setPlainText(seq)
            self._fasta_path_lbl.setText(os.path.basename(path))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _browse_msa(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select MSA file", "", "A3M (*.a3m);;All files (*)"
        )
        if path:
            self._msa_edit.setText(path)

    def _browse_cif(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select template CIF", "", "CIF (*.cif);;All files (*)"
        )
        if path:
            self._cif_edit.setText(path)

    def _browse_outdir(self):
        start = self._outdir_edit.text().strip() or self._settings.value(_KEY_OUTDIR, "")
        path = QFileDialog.getExistingDirectory(self, "Select output directory", start)
        if path:
            self._outdir_edit.setText(path)
            self._settings.setValue(_KEY_OUTDIR, path)

    def _query_colabfold(self):
        seq = self._seq_edit.toPlainText().strip()
        if not seq:
            QMessageBox.warning(self, "No sequence", "Please enter a protein sequence first.")
            return
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save MSA as", "msa.a3m", "A3M (*.a3m)"
        )
        if not out_path:
            return
        self.msa_query_requested.emit(seq, out_path)

    def _on_generate(self):
        params = self._collect_yaml_params()
        self._settings.setValue(_KEY_OUTDIR, params.output_dir)
        self.yaml_requested.emit(params)

    def _collect_yaml_params(self) -> YAMLParams:
        return YAMLParams(
            mode="affinity" if self._affinity_rb.isChecked() else "template",
            protein_sequence=self._seq_edit.toPlainText().strip(),
            msa_path=self._msa_edit.text().strip(),
            output_dir=self._outdir_edit.text().strip() or "yaml_output",
            n_dirs=self._ndirs_spin.value(),
            template_cif_path=self._cif_edit.text().strip(),
        )

    # ── Public helpers ────────────────────────────────────────────────

    def set_protein_sequence(self, seq: str):
        self._seq_edit.setPlainText(seq)

    def set_msa_path(self, path: str):
        self._msa_edit.setText(path)

    def set_msa_busy(self, busy: bool, status: str = ""):
        self._colabfold_btn.setEnabled(not busy)
        self._msa_progress.setVisible(busy)
        self._msa_status_lbl.setText(status)

    def set_msa_progress(self, pct: int):
        self._msa_progress.setValue(pct)

    def set_yaml_busy(self, busy: bool, status: str = ""):
        self._gen_btn.setEnabled(not busy)
        self._yaml_progress.setVisible(busy)
        self._yaml_status_lbl.setText(status)
        self._gen_btn.setText("Generating…" if busy else "Generate YAML Files")

    def set_yaml_progress(self, pct: int):
        self._yaml_progress.setValue(pct)

    def get_source_choice(self) -> str:
        return self._src_combo.currentText()

    def suggest_ndirs(self, n_compounds: int):
        self._ndirs_spin.setValue(8 if n_compounds > 500 else 4)
