from PyQt5.QtCore import QThread, pyqtSignal

from core.msa.colabfold_client import submit_msa_job, poll_job, download_msa


class MSAWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)   # path to .a3m file
    error = pyqtSignal(str)

    def __init__(self, sequence: str, output_path: str, parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self.output_path = output_path

    def run(self):
        try:
            self.status.emit("Submitting MSA job to ColabFold…")
            self.progress.emit(5)
            job_id, job_status, query = submit_msa_job(self.sequence)

            self.status.emit(f"Job submitted (id={job_id}). Waiting for results…")
            self.progress.emit(10)

            while not self.isInterruptionRequested():
                if job_status in ("PENDING", "RUNNING", "UNKNOWN"):
                    job_status, job_id = poll_job(job_id, query)
                if job_status == "COMPLETE":
                    break
                if job_status == "ERROR":
                    self.error.emit("ColabFold MSA job failed on the server.")
                    return
                self.status.emit(f"MSA status: {job_status}…")
                self.msleep(5000)

            if self.isInterruptionRequested():
                return

            self.status.emit("Downloading MSA result…")
            self.progress.emit(80)
            path, used_fallback = download_msa(job_id, self.output_path, query)
            if used_fallback:
                self.status.emit("ColabFold returned a non-downloadable result; using single-sequence A3M fallback.")
            self.progress.emit(100)
            self.finished.emit(path)

        except Exception as exc:
            self.error.emit(str(exc))
