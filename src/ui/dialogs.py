from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView
)

class DuplicatesPreviewDialog(QDialog):
    """
    Show duplicates and let user continue (skip them) or cancel import.
    """
    def __init__(self, parent, duplicates):
        super().__init__(parent)
        self.setWindowTitle("Duplicati trovati")
        self.proceed = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Queste righe sono duplicate (già presenti nel progetto) e verranno SCARTATE:"))

        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Data", "Voce", "Dettaglio", "Importo"])
        table.setRowCount(len(duplicates))

        for i, r in enumerate(duplicates):
            for j, val in enumerate(r):
                table.setItem(i, j, QTableWidgetItem(str(val)))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        btns = QHBoxLayout()
        cancel = QPushButton("Annulla import")
        ok = QPushButton("Scarta duplicati e continua")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._on_ok)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

    def _on_ok(self):
        self.proceed = True
        self.accept()
