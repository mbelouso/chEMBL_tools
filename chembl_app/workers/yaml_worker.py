import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

from core.io.yaml_generator import YAMLParams, generate_yaml_files


class YAMLWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)   # output directory
    error = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, params: YAMLParams, parent=None):
        super().__init__(parent)
        self.df = df
        self.params = params

    def run(self):
        try:
            self.status.emit(f"Generating {len(self.df)} YAML files…")

            def _cb(pct: int):
                self.progress.emit(pct)
                if self.isInterruptionRequested():
                    raise InterruptedError("Cancelled")

            generate_yaml_files(self.df, self.params, progress_cb=_cb)
            self.progress.emit(100)
            self.finished.emit(self.params.output_dir)
        except InterruptedError:
            pass
        except Exception as exc:
            self.error.emit(str(exc))
