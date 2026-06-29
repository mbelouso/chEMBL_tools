import os
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QProgressBar,
    QMenuBar, QAction, QMessageBox,
)
from PyQt5.QtCore import Qt

from models.app_state import AppState
from app.tabs.search_tab import SearchTab
from app.tabs.diversity_tab import DiversityTab
from app.tabs.boltz_tab import BoltzTab
from app.dialogs.settings_dialog import SettingsDialog
from workers.search_worker import SearchWorker
from workers.diversity_worker import DiversityWorker
from workers.yaml_worker import YAMLWorker
from workers.msa_worker import MSAWorker
from core.db.connection import get_connection
from core.io.csv_export import export_csv


class MainWindow(QMainWindow):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setWindowTitle("ChEMBL Tools")
        self.resize(1280, 800)

        self._search_worker: SearchWorker = None
        self._diversity_worker: DiversityWorker = None
        self._yaml_worker: YAMLWorker = None
        self._msa_worker: MSAWorker = None

        self._build_menu()
        self._build_ui()

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("File")

        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = mb.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_ui(self):
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._search_tab = SearchTab()
        self._diversity_tab = DiversityTab()
        self._boltz_tab = BoltzTab()

        self._tabs.addTab(self._search_tab, "Search")
        self._tabs.addTab(self._diversity_tab, "Diversity Filter")
        self._tabs.addTab(self._boltz_tab, "Boltz-2 YAML Export")

        # Status bar + progress
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._progress = QProgressBar()
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress)

        # Wire signals
        self._search_tab.search_requested.connect(self._on_search_requested)
        self._search_tab.export_requested.connect(self._on_search_export_requested)
        self._search_tab.curation_changed.connect(self._on_search_curation_changed)
        self._diversity_tab.cluster_requested.connect(self._on_cluster_requested)
        self._diversity_tab.curation_changed.connect(self._on_diversity_curation_changed)
        self._diversity_tab.export_requested.connect(self._on_export_requested)
        self._boltz_tab.yaml_requested.connect(self._on_yaml_requested)
        self._boltz_tab.msa_query_requested.connect(self._on_msa_requested)

        # Kick off target-name loading if db is already configured
        if self.state.db_path and os.path.isfile(self.state.db_path):
            self._search_tab.set_db_path(self.state.db_path)

    # ── Search ────────────────────────────────────────────────────────

    def _on_search_requested(self, params):
        if not self.state.db_path or not os.path.isfile(self.state.db_path):
            self._open_settings(mandatory=True)
            if not self.state.db_path:
                return
            self._search_tab.set_db_path(self.state.db_path)

        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.requestInterruption()
            self._search_worker.wait()

        self._search_tab.set_busy(True)
        self._show_progress(True)
        self._status_bar.showMessage("Searching…")

        self._search_worker = SearchWorker(self.state.db_path, params)
        self._search_worker.progress.connect(self._progress.setValue)
        self._search_worker.status.connect(self._status_bar.showMessage)
        self._search_worker.results_ready.connect(self._on_search_complete)
        self._search_worker.plot_ready.connect(self._search_tab.tsne_canvas.set_figure)
        self._search_worker.pca_plot_ready.connect(self._search_tab.pca_canvas.set_figure)
        self._search_worker.error.connect(self._on_error)
        self._search_worker.finished.connect(lambda: self._search_tab.set_busy(False))
        self._search_worker.finished.connect(lambda: self._show_progress(False))
        self._search_worker.start()

    def _on_search_complete(self, df, fps_array, tsne_coords):
        self.state.current_results = df
        self.state.curated_results = df
        self.state.fps_array = fps_array
        self.state.curated_fps_array = fps_array
        self.state.tsne_coords = tsne_coords
        self.state.curated_tsne_coords = tsne_coords
        self.state.diversity_results = None
        self.state.diversity_curated_results = None

        self._search_tab.set_search_results(df)

        self._diversity_tab.setEnabled(True)
        self._boltz_tab.setEnabled(True)
        self._boltz_tab.suggest_ndirs(len(df))

        self._status_bar.showMessage(f"Found {len(df)} compounds.")

    def _on_search_curation_changed(self, curated_df):
        if self.state.current_results is None:
            return

        self.state.curated_results = curated_df
        if curated_df is None:
            self.state.curated_fps_array = None
            self.state.curated_tsne_coords = None
            return

        if self.state.fps_array is None or self.state.tsne_coords is None:
            return

        row_idx = curated_df.index.to_numpy(dtype=int)
        self.state.curated_fps_array = self.state.fps_array[row_idx]
        self.state.curated_tsne_coords = self.state.tsne_coords[row_idx]
        self._boltz_tab.suggest_ndirs(len(curated_df))
        self._status_bar.showMessage(
            f"Curated subset: {len(curated_df)}/{len(self.state.current_results)} compounds."
        )

    def _get_active_search_inputs(self):
        if self.state.curated_results is not None and self.state.curated_fps_array is not None:
            return self.state.curated_results, self.state.curated_fps_array, self.state.curated_tsne_coords
        return self.state.current_results, self.state.fps_array, self.state.tsne_coords

    # ── Diversity ─────────────────────────────────────────────────────

    def _on_cluster_requested(self, params):
        if self.state.current_results is None:
            return
        if self._diversity_worker and self._diversity_worker.isRunning():
            self._diversity_worker.requestInterruption()
            self._diversity_worker.wait()

        self._diversity_tab.set_busy(True)
        self._show_progress(True)

        active_df, active_fps, active_tsne = self._get_active_search_inputs()

        self._diversity_worker = DiversityWorker(
            active_df,
            active_fps,
            active_tsne,
            params,
        )
        self._diversity_worker.progress.connect(self._progress.setValue)
        self._diversity_worker.status.connect(self._status_bar.showMessage)
        self._diversity_worker.results_ready.connect(self._on_diversity_complete)
        self._diversity_worker.pre_plot_ready.connect(self._diversity_tab.set_pre_filter_plot)
        self._diversity_worker.plot_ready.connect(self._diversity_tab.post_tsne_canvas.set_figure)
        self._diversity_worker.overlay_ready.connect(self._on_diversity_overlay_ready)
        self._diversity_worker.summary_ready.connect(self._diversity_tab.set_summary)
        self._diversity_worker.error.connect(self._on_error)
        self._diversity_worker.finished.connect(lambda: self._diversity_tab.set_busy(False))
        self._diversity_worker.finished.connect(lambda: self._show_progress(False))
        self._diversity_worker.start()

    def _on_diversity_complete(self, df):
        self.state.diversity_results = df
        self.state.diversity_curated_results = df
        self._diversity_tab.on_results_ready(df)
        self._diversity_tab.post_tsne_canvas.set_dataframe(df)
        self._status_bar.showMessage(f"Diversity filter: {len(df)} compounds retained.")

    def _on_diversity_overlay_ready(self, df_pre, df_diverse):
        self._diversity_tab.set_overlay_plot(None, df_pre)

    def _on_diversity_curation_changed(self, curated_df):
        self.state.diversity_curated_results = curated_df
        base_n = len(self.state.diversity_results) if self.state.diversity_results is not None else 0
        cur_n = len(curated_df) if curated_df is not None else 0
        if base_n > 0:
            self._status_bar.showMessage(f"Diversity curated: {cur_n}/{base_n} compounds.")

    # ── Export ────────────────────────────────────────────────────────

    def _on_export_requested(self, output_path: str):
        df = (
            self.state.diversity_curated_results
            if self.state.diversity_curated_results is not None
            else (self.state.diversity_results if self.state.diversity_results is not None else self.state.current_results)
        )
        if df is None:
            return
        try:
            with get_connection(self.state.db_path) as conn:
                export_csv(df, conn, output_path)
            self._status_bar.showMessage(f"Exported to {output_path}")
            QMessageBox.information(self, "Export complete", f"Results saved to:\n{output_path}")
        except Exception as e:
            self._on_error(str(e))

    def _on_search_export_requested(self, output_path: str):
        df = self.state.curated_results if self.state.curated_results is not None else self.state.current_results
        if df is None:
            return
        try:
            with get_connection(self.state.db_path) as conn:
                export_csv(df, conn, output_path)
            self._status_bar.showMessage(f"Exported search results to {output_path}")
            QMessageBox.information(self, "Export complete", f"Results saved to:\n{output_path}")
        except Exception as e:
            self._on_error(str(e))

    # ── YAML ──────────────────────────────────────────────────────────

    def _on_yaml_requested(self, params):
        choice = self._boltz_tab.get_source_choice()
        active_search_df, _, _ = self._get_active_search_inputs()
        df = (
            (self.state.diversity_curated_results if self.state.diversity_curated_results is not None else self.state.diversity_results)
            if "Diversity" in choice and (self.state.diversity_results is not None or self.state.diversity_curated_results is not None)
            else active_search_df
        )
        if df is None:
            QMessageBox.warning(self, "No data", "Run a search first.")
            return
        if not params.protein_sequence:
            QMessageBox.warning(self, "No sequence", "Enter a protein sequence first.")
            return

        if self._yaml_worker and self._yaml_worker.isRunning():
            self._yaml_worker.requestInterruption()
            self._yaml_worker.wait()

        self._boltz_tab.set_yaml_busy(True, "Generating YAML files…")
        self._show_progress(True)

        self._yaml_worker = YAMLWorker(df, params)
        self._yaml_worker.progress.connect(self._progress.setValue)
        self._yaml_worker.progress.connect(self._boltz_tab.set_yaml_progress)
        self._yaml_worker.status.connect(lambda s: self._boltz_tab.set_yaml_busy(True, s))
        self._yaml_worker.finished.connect(self._on_yaml_done)
        self._yaml_worker.error.connect(self._on_error)
        self._yaml_worker.finished.connect(lambda _: self._boltz_tab.set_yaml_busy(False))
        self._yaml_worker.finished.connect(lambda _: self._show_progress(False))
        self._yaml_worker.start()

    def _on_yaml_done(self, output_dir: str):
        self._status_bar.showMessage(f"YAML files written to {output_dir}")
        QMessageBox.information(self, "Done", f"YAML files generated in:\n{output_dir}")

    # ── MSA ───────────────────────────────────────────────────────────

    def _on_msa_requested(self, sequence: str, output_path: str):
        if self._msa_worker and self._msa_worker.isRunning():
            self._msa_worker.requestInterruption()
            self._msa_worker.wait()

        self._boltz_tab.set_msa_busy(True, "Submitting to ColabFold…")

        self._msa_worker = MSAWorker(sequence, output_path)
        self._msa_worker.progress.connect(self._boltz_tab.set_msa_progress)
        self._msa_worker.status.connect(lambda s: self._boltz_tab.set_msa_busy(True, s))
        self._msa_worker.finished.connect(self._on_msa_done)
        self._msa_worker.error.connect(self._on_error)
        self._msa_worker.finished.connect(lambda _: self._boltz_tab.set_msa_busy(False))
        self._msa_worker.start()

    def _on_msa_done(self, path: str):
        self._boltz_tab.set_msa_path(path)
        self._status_bar.showMessage(f"MSA saved to {path}")

    # ── Helpers ───────────────────────────────────────────────────────

    def _show_progress(self, visible: bool):
        self._progress.setVisible(visible)
        if visible:
            self._progress.setValue(0)

    def _on_error(self, msg: str):
        self._show_progress(False)
        self._search_tab.set_busy(False)
        self._diversity_tab.set_busy(False)
        self._boltz_tab.set_yaml_busy(False)
        self._boltz_tab.set_msa_busy(False)
        self._status_bar.showMessage(f"Error: {msg}")
        QMessageBox.critical(self, "Error", msg)

    def _open_settings(self, mandatory: bool = False):
        dlg = SettingsDialog(self, mandatory=mandatory)
        if dlg.exec_():
            self.state.db_path = dlg.db_path()
            self._search_tab.set_db_path(self.state.db_path)

    def _show_about(self):
        QMessageBox.about(
            self,
            "ChEMBL Tools",
            "ChEMBL compound search, diversity filtering, and Boltz-2 YAML export.\n\n"
            "Built with PyQt5, RDKit, scikit-learn, and the ChEMBL SQLite database.",
        )

    def closeEvent(self, event):
        for w in (self._search_worker, self._diversity_worker, self._yaml_worker, self._msa_worker):
            if w and w.isRunning():
                w.requestInterruption()
                w.wait()
        event.accept()
