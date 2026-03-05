from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt

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


class SimilarTransactionsDialog(QDialog):
    """
    Show similar transactions and let user choose which ones to update.
    """
    def __init__(self, parent, similar_rows):
        super().__init__(parent)
        self.setWindowTitle("Applica categoria a movimenti simili")
        self.selected_ids = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Seleziona i movimenti con stessa Voce e stesso Dettaglio a cui applicare la stessa categoria:"))

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Applica", "Data", "Voce", "Dettaglio", "Importo"])
        self.table.setRowCount(len(similar_rows))

        for i, row in enumerate(similar_rows):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox_item.setCheckState(Qt.Checked)
            checkbox_item.setData(Qt.UserRole, int(row["id"]))
            self.table.setItem(i, 0, checkbox_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(row["date_value"] or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["voice_raw"] or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(row["detail_raw"] or "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(row["amount"] or "")))

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        select_all = QPushButton("Seleziona tutto")
        deselect_all = QPushButton("Deseleziona tutto")
        cancel = QPushButton("Annulla")
        ok = QPushButton("Conferma")

        select_all.clicked.connect(lambda: self._set_all_checkboxes(Qt.Checked))
        deselect_all.clicked.connect(lambda: self._set_all_checkboxes(Qt.Unchecked))
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._on_ok)

        btns.addWidget(select_all)
        btns.addWidget(deselect_all)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

    def _set_all_checkboxes(self, state):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item is not None:
                item.setCheckState(state)

    def _on_ok(self):
        selected = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected.append(int(item.data(Qt.UserRole)))
        self.selected_ids = selected
        self.accept()
