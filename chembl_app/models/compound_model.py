import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex


class CompoundTableModel(QAbstractTableModel):
    _DISPLAY_COLS = [
        "chembl_id", "canonical_smiles", "molecular_weight", "alogp",
        "hba", "hbd", "psa",
        "target_name", "target_chembl_id", "target_uniprot",
        "best_ic50_nm", "best_ec50_nm", "best_ki_nm", "purchasable",
    ]
    _HEADERS = [
        "ChEMBL ID", "SMILES", "MW", "LogP", "HBA", "HBD", "PSA",
        "Target Name", "Target ChEMBL", "UniProt",
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
        return len(self._cols) + 1  # +1 for the row-number column

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return str(index.row() + 1)
            col = self._cols[index.column() - 1]
            val = self._df.iloc[index.row()][col]
            if isinstance(val, float):
                return f"{val:.3f}"
            return str(val) if val is not None and not (isinstance(val, float) and pd.isna(val)) else ""
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section == 0:
                return "#"
            return self._headers[section - 1]
        return None

    def get_dataframe(self) -> pd.DataFrame:
        return self._df
