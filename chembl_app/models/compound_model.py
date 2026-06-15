import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex


class CompoundTableModel(QAbstractTableModel):
    _DISPLAY_COLS = [
        "chembl_id", "canonical_smiles", "molecular_weight", "alogp",
        "hba", "hbd", "psa", "best_ic50_nm", "best_ec50_nm", "best_ki_nm", "purchasable",
    ]
    _HEADERS = [
        "ChEMBL ID", "SMILES", "MW", "LogP", "HBA", "HBD", "PSA",
        "IC50 best (nM)", "EC50 best (nM)", "Ki best (nM)", "Purchasable",
    ]

    def __init__(self, df: pd.DataFrame = None, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame() if df is None else df
        self._cols = [c for c in self._DISPLAY_COLS if c in self._df.columns]
        self._headers = [
            self._HEADERS[self._DISPLAY_COLS.index(c)] for c in self._cols
        ]

    def update_data(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self._cols = [c for c in self._DISPLAY_COLS if c in self._df.columns]
        self._headers = [
            self._HEADERS[self._DISPLAY_COLS.index(c)] for c in self._cols
        ]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._cols)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            val = self._df.iloc[index.row()][self._cols[index.column()]]
            if isinstance(val, float):
                return f"{val:.3f}"
            return str(val) if val is not None and not (isinstance(val, float) and pd.isna(val)) else ""
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def get_dataframe(self) -> pd.DataFrame:
        return self._df
