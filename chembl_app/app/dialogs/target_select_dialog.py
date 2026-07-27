from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QDialogButtonBox,
)
from PyQt5.QtCore import Qt


class TargetSelectDialog(QDialog):
    def __init__(self, names: list, selected: list = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Targets")
        self.setMinimumSize(480, 560)

        selected_set = set(selected or [])

        layout = QVBoxLayout(self)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter targets…")
        self._filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_edit)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)  # perf: skip per-row size hint recompute
        self._list.setUpdatesEnabled(False)
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in selected_set else Qt.Unchecked)
            self._list.addItem(item)
        self._list.setUpdatesEnabled(True)
        self._list.itemChanged.connect(self._update_count_label)
        layout.addWidget(self._list, stretch=1)

        action_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All Filtered")
        select_all_btn.clicked.connect(self._select_all_filtered)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        action_row.addWidget(select_all_btn)
        action_row.addWidget(clear_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        bottom_row = QHBoxLayout()
        self._count_label = QLabel()
        bottom_row.addWidget(self._count_label)
        bottom_row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom_row.addWidget(buttons)
        layout.addLayout(bottom_row)

        self._update_count_label()

    def _apply_filter(self, text: str):
        text = text.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _select_all_filtered(self):
        self._list.itemChanged.disconnect(self._update_count_label)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)
        self._list.itemChanged.connect(self._update_count_label)
        self._update_count_label()

    def _clear_all(self):
        self._list.itemChanged.disconnect(self._update_count_label)
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.Unchecked)
        self._list.itemChanged.connect(self._update_count_label)
        self._update_count_label()

    def _update_count_label(self, *_args):
        n = sum(
            1 for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.Checked
        )
        self._count_label.setText(f"{n} selected")

    def selected_names(self) -> list:
        return [
            self._list.item(i).text()
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.Checked
        ]
