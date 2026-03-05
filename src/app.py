import sys
from typing import Optional

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from db import DB
from ui.main_window import MainWindow

def choose_db_path() -> Optional[str]:
    choice = QMessageBox.question(
        None,
        "Progetto",
        "Vuoi aprire un progetto esistente o crearne uno nuovo?",
        QMessageBox.Open | QMessageBox.Save | QMessageBox.Cancel,
        QMessageBox.Open,
    )

    if choice == QMessageBox.Cancel:
        return None

    if choice == QMessageBox.Open:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Apri progetto (database)",
            "",
            "Database SQLite (*.db);;Tutti i file (*.*)",
        )
        return path or None

    path, _ = QFileDialog.getSaveFileName(
        None,
        "Crea nuovo progetto (database)",
        "spese.db",
        "Database SQLite (*.db)",
    )
    return path or None

def main():
    app = QApplication(sys.argv)

    path = choose_db_path()
    if not path:
        QMessageBox.information(None, "Info", "Nessun file selezionato.")
        sys.exit(0)

    db = DB(path)
    db.init_schema()

    w = MainWindow(db)
    w.resize(1400, 850)
    w.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
