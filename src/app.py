import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from db import DB
from ui.main_window import MainWindow

LAST_PROJECT_FILE = Path.home() / ".famwallet_last_project"


def get_last_project_path() -> Optional[str]:
    if not LAST_PROJECT_FILE.exists():
        return None
    path = LAST_PROJECT_FILE.read_text(encoding="utf-8").strip()
    if not path:
        return None
    return path if Path(path).exists() else None


def save_last_project_path(path: str):
    LAST_PROJECT_FILE.write_text(path, encoding="utf-8")

def choose_db_path() -> Optional[str]:
    last_path = get_last_project_path()
    if last_path:
        choice = QMessageBox.question(
            None,
            "Progetto",
            f"Ho trovato l'ultimo progetto usato:\n{last_path}\n\nVuoi riaprirlo?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if choice == QMessageBox.Yes:
            return last_path
        if choice == QMessageBox.Cancel:
            return None

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
    save_last_project_path(path)

    w = MainWindow(db)
    w.resize(1400, 850)
    w.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
