from PyQt5.QtCore import QThread, pyqtSignal
from core.db.connection import get_connection
from core.db.queries import query_all_target_names


class TargetNamesWorker(QThread):
    names_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path

    def run(self):
        try:
            with get_connection(self.db_path) as conn:
                names = query_all_target_names(conn)
            self.names_ready.emit(names)
        except Exception as exc:
            self.error.emit(str(exc))
