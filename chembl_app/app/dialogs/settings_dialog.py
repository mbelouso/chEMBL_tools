import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, QMessageBox,
)
from PyQt5.QtCore import QSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None, mandatory: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Settings — ChEMBL Database")
        self.setMinimumWidth(500)
        self._mandatory = mandatory

        self._settings = QSettings("chEMBL_tools", "ChEMBLSearch")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("ChEMBL SQLite database path:"))

        row = QHBoxLayout()
        self._path_edit = QLineEdit(self._settings.value("db_path", ""))
        row.addWidget(self._path_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        layout.addWidget(QLabel(
            "Example: chembl_37/chembl_37_sqlite/chembl_37.db"
        ))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if mandatory:
            buttons.button(QDialogButtonBox.Cancel).setEnabled(False)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select ChEMBL database", "", "SQLite (*.db *.sqlite);;All files (*)"
        )
        if path:
            self._path_edit.setText(path)

    def _accept(self):
        path = self._path_edit.text().strip()
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Invalid path", "The selected file does not exist.")
            return
        self._settings.setValue("db_path", path)
        self.accept()

    def db_path(self) -> str:
        return self._path_edit.text().strip()

    @staticmethod
    def get_saved_db_path() -> str:
        s = QSettings("chEMBL_tools", "ChEMBLSearch")
        return s.value("db_path", "")
