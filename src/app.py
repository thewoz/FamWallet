import sys
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from db import DB
from ui.main_window import MainWindow

def choose_db_path() -> str | None:
    # Let user pick an existing .db or type a new one
    path, _ = QFileDialog.getSaveFileName(
        None,
        "Apri o crea progetto (database)",
        "spese.db",
        "Database SQLite (*.db)"
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
