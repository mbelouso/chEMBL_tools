import pandas as pd
from PyQt5.QtWidgets import QTableView, QAbstractItemView, QSizePolicy
from PyQt5.QtCore import Qt
from models.compound_model import CompoundTableModel


class ResultsTable(QTableView):
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

    def update_data(self, df: pd.DataFrame):
        self._model.update_data(df)
        self.resizeColumnsToContents()

    def get_dataframe(self) -> pd.DataFrame:
        return self._model.get_dataframe()
