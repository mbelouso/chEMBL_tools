import sys
import os

# Ensure chembl_app/ is on the path so all relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication

from models.app_state import AppState
from app.main_window import MainWindow
from app.dialogs.settings_dialog import SettingsDialog


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ChEMBL Tools")
    app.setOrganizationName("chEMBL_tools")

    state = AppState()

    # Load saved DB path; prompt if missing or invalid
    saved = SettingsDialog.get_saved_db_path()
    if saved and os.path.isfile(saved):
        state.db_path = saved
    else:
        dlg = SettingsDialog(mandatory=True)
        if dlg.exec_():
            state.db_path = dlg.db_path()
        else:
            sys.exit(0)

    window = MainWindow(state)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
