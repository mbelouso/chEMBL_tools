import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QTableView, QAbstractItemView, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from models.compound_model import CompoundTableModel


class ResultsTable(QTableView):
    row_selected = pyqtSignal(str, str)  # (smiles, chembl_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = CompoundTableModel()
        self.setModel(self._model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def update_data(self, df: pd.DataFrame):
        self._model.update_data(df)
        self.resizeColumnsToContents()
        # Re-wire after model reset since selectionModel may be recreated
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, selected, deselected):
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        df = self._model.get_dataframe()
        if df.empty or row >= len(df):
            return
        record = df.iloc[row]
        smiles = str(record.get("canonical_smiles", ""))
        chembl_id = str(record.get("chembl_id", ""))
        if smiles:
            self.row_selected.emit(smiles, chembl_id)

    def get_dataframe(self) -> pd.DataFrame:
        return self._model.get_dataframe()

    def select_by_chembl_id(self, chembl_id: str) -> bool:
        """Select (and scroll to) the row matching chembl_id. Returns False if not found."""
        df = self._model.get_dataframe()
        if df.empty or "chembl_id" not in df.columns or not chembl_id:
            return False
        positions = np.flatnonzero(df["chembl_id"].astype(str).to_numpy() == str(chembl_id))
        if positions.size == 0:
            return False
        row = int(positions[0])
        self.selectRow(row)
        self.scrollTo(self._model.index(row, 0))
        return True
