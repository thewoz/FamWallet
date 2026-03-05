from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QComboBox, QCheckBox, QSplitter, QTableView, QFormLayout,
    QLineEdit, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QItemSelectionModel
import sqlite3

from db import DB
from importer import preview_import
from normalizer import normalize_text
from charts import PieChartWidget, build_pie_by_category
from ui.dialogs import DuplicatesPreviewDialog, SimilarTransactionsDialog


class TxTableModel(QAbstractTableModel):
    COLS = ["Data", "Voce", "Dettaglio", "Importo", "Categoria", "Sotto-categoria", "Escludi"]

    def __init__(self, rows, db: DB):
        super().__init__()
        self.rows = list(rows)
        self.db = db

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.COLS[section]
        return str(section + 1)

    def _voice_display(self, row: dict) -> str:
        alias = self.db.get_alias(row["voice_norm"], row["detail_norm"])
        return alias if alias else (row["voice_raw"] or "")

    def _sort_key(self, row: dict, column: int):
        if column == 0:
            return row["date_value"] or ""
        if column == 1:
            return self._voice_display(row).lower()
        if column == 2:
            return (row["detail_raw"] or "").lower()
        if column == 3:
            amount = str(row["amount"] or "0").replace(",", ".")
            try:
                return float(amount)
            except ValueError:
                return 0.0
        if column == 4:
            return (row["category_name"] or "").lower()
        if column == 5:
            return (row["subcategory_name"] or "").lower()
        if column == 6:
            return int(row["excluded"])
        return ""

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        r = self.rows[index.row()]
        c = index.column()

        if role == Qt.DisplayRole:
            if c == 0:
                return r["date_value"] or ""
            if c == 1:
                return self._voice_display(r)
            if c == 2:
                return r["detail_raw"] or ""
            if c == 3:
                return r["amount"] or ""
            if c == 4:
                return r["category_name"] or ""
            if c == 5:
                return r["subcategory_name"] or ""

        if role == Qt.CheckStateRole and c == 6:
            return Qt.Checked if int(r["excluded"]) == 1 else Qt.Unchecked

        if role == Qt.TextAlignmentRole and c == 3:
            return Qt.AlignRight | Qt.AlignVCenter

        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        if index.column() == 6:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        if index.column() == 6 and role == Qt.CheckStateRole:
            r = dict(self.rows[index.row()])
            r["excluded"] = 1 if value == Qt.Checked else 0
            self.rows[index.row()] = r
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def sort(self, column, order=Qt.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        reverse = order == Qt.DescendingOrder
        self.rows.sort(key=lambda row: self._sort_key(row, column), reverse=reverse)
        self.layoutChanged.emit()

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def get_row(self, i: int):
        return self.rows[i]


class MainWindow(QMainWindow):
    def __init__(self, db: DB):
        super().__init__()
        self.db = db

        self.current_tx_id = None
        self.category_filter = None
        self.uncategorized_filter = False
        self.show_excluded = False
        self.exclude_category_name = "Eliminati"

        self.setWindowTitle(f"Spese (progetto: {db.path})")

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        top = QHBoxLayout()

        self.btn_import = QPushButton("Importa CSV…")
        self.btn_import.clicked.connect(self.on_import)
        top.addWidget(self.btn_import)

        top.addSpacing(12)
        top.addWidget(QLabel("Filtro:"))

        self.cmb_cat_filter = QComboBox()
        self.cmb_cat_filter.currentIndexChanged.connect(self.on_filter_changed)
        top.addWidget(self.cmb_cat_filter)

        self.chk_show_excl = QCheckBox("Mostra esclusi")
        self.chk_show_excl.setChecked(False)
        self.chk_show_excl.stateChanged.connect(self.on_filter_changed)
        top.addWidget(self.chk_show_excl)

        top.addStretch(1)
        self.lbl_stats = QLabel("—")
        top.addWidget(self.lbl_stats)

        root_layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.clicked.connect(self.on_row_selected)
        left_layout.addWidget(self.table, 3)

        self.chart = PieChartWidget()
        left_layout.addWidget(self.chart, 2)

        splitter.addWidget(left)

        right = QWidget()
        form = QFormLayout(right)

        self.txt_voice = QLineEdit()
        self.txt_detail = QLineEdit()
        self.txt_detail.setReadOnly(True)

        self.btn_rename_voice = QPushButton("Rinomina voce")
        self.btn_rename_voice.clicked.connect(self.on_rename_voice)

        self.txt_alias = QLineEdit()
        self.btn_save_alias = QPushButton("Salva alias (Voce+Dettaglio)")
        self.btn_save_alias.clicked.connect(self.on_save_alias)

        alias_row = QHBoxLayout()
        alias_row.addWidget(self.txt_alias, 1)
        alias_row.addWidget(self.btn_save_alias)

        self.cmb_cat = QComboBox()
        self.cmb_sub = QComboBox()
        self.cmb_cat.currentIndexChanged.connect(self.refresh_subcategories)

        self.btn_add_cat = QPushButton("Nuova categoria…")
        self.btn_add_cat.clicked.connect(self.on_add_category)
        self.btn_rename_cat = QPushButton("Rinomina categoria…")
        self.btn_rename_cat.clicked.connect(self.on_rename_category)

        self.btn_add_sub = QPushButton("Nuova sotto-categoria…")
        self.btn_add_sub.clicked.connect(self.on_add_subcategory)
        self.btn_rename_sub = QPushButton("Rinomina sotto-categoria…")
        self.btn_rename_sub.clicked.connect(self.on_rename_subcategory)

        self.btn_apply = QPushButton("Applica categoria")
        self.btn_apply.clicked.connect(self.on_apply_category)

        form.addRow("Voce:", self.txt_voice)
        form.addRow("", self.btn_rename_voice)
        form.addRow("Dettaglio:", self.txt_detail)
        form.addRow("Alias:", alias_row)
        form.addRow("Categoria:", self.cmb_cat)
        form.addRow("", self.btn_add_cat)
        form.addRow("", self.btn_rename_cat)
        form.addRow("Sotto-categoria:", self.cmb_sub)
        form.addRow("", self.btn_add_sub)
        form.addRow("", self.btn_rename_sub)
        form.addRow("", self.btn_apply)

        splitter.addWidget(right)
        splitter.setSizes([950, 450])

        self.model = TxTableModel([], self.db)
        self.table.setModel(self.model)
        self.model.dataChanged.connect(self.on_table_data_changed)

        self.refresh_categories()
        self.refresh_filter_combo()
        self.refresh_view()

    def refresh_categories(self):
        cats = self.db.list_categories()
        current_cat_id = self.cmb_cat.currentData()

        self.cmb_cat.blockSignals(True)
        self.cmb_cat.clear()
        self.cmb_cat.addItem("—", None)
        for c in cats:
            self.cmb_cat.addItem(c["name"], int(c["id"]))
        if current_cat_id is not None:
            idx = self.cmb_cat.findData(int(current_cat_id))
            self.cmb_cat.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_cat.blockSignals(False)
        self.refresh_subcategories()

    def refresh_subcategories(self):
        cat_id = self.cmb_cat.currentData()
        current_sub_id = self.cmb_sub.currentData()

        self.cmb_sub.blockSignals(True)
        self.cmb_sub.clear()
        self.cmb_sub.addItem("—", None)
        if cat_id is not None:
            subs = self.db.list_subcategories(int(cat_id))
            for s in subs:
                self.cmb_sub.addItem(s["name"], int(s["id"]))
        if current_sub_id is not None:
            idx = self.cmb_sub.findData(int(current_sub_id))
            self.cmb_sub.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_sub.blockSignals(False)

    def refresh_filter_combo(self):
        prev = self.cmb_cat_filter.currentData()
        self.cmb_cat_filter.blockSignals(True)
        self.cmb_cat_filter.clear()
        self.cmb_cat_filter.addItem("Tutte le spese", ("ALL", None))
        self.cmb_cat_filter.addItem("Senza categoria", ("UNCAT", None))
        for c in self.db.list_categories():
            self.cmb_cat_filter.addItem(f"Solo: {c['name']}", ("CAT", int(c["id"])))
        self.cmb_cat_filter.blockSignals(False)

        idx = -1
        for i in range(self.cmb_cat_filter.count()):
            if self.cmb_cat_filter.itemData(i) == prev:
                idx = i
                break
        self.cmb_cat_filter.setCurrentIndex(idx if idx >= 0 else 0)

    def refresh_view(self):
        selected_ids = self._selected_transaction_ids()
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()

        rows = self.db.fetch_transactions(
            category_filter=self.category_filter,
            uncategorized=self.uncategorized_filter,
            show_excluded=self.show_excluded,
        )
        self.model.set_rows(rows)
        if self.table.isSortingEnabled() and sort_col >= 0:
            self.table.sortByColumn(sort_col, sort_order)
        self.table.resizeColumnsToContents()
        self._restore_selection_by_ids(selected_ids)
        self.refresh_stats(rows)
        self.refresh_chart(rows)

    def _exclude_category_id(self):
        for c in self.db.list_categories():
            if c["name"] == self.exclude_category_name:
                return int(c["id"])
        return None

    def _selected_transaction_ids(self):
        indexes = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return [int(self.model.get_row(idx.row())["id"]) for idx in indexes]

    def _restore_selection_by_ids(self, tx_ids):
        if not tx_ids or not self.table.selectionModel():
            return
        selected = set(int(tx_id) for tx_id in tx_ids)
        selection_model = self.table.selectionModel()
        for row_idx, row in enumerate(self.model.rows):
            if int(row["id"]) in selected:
                idx = self.model.index(row_idx, 0)
                selection_model.select(idx, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def refresh_stats(self, rows):
        total = len(rows)
        excl = sum(1 for r in rows if int(r["excluded"]) == 1)
        unc = sum(1 for r in rows if r["category_id"] is None and int(r["excluded"]) == 0)
        self.lbl_stats.setText(f"Movimenti: {total} — Esclusi: {excl} — Senza categoria: {unc}")

    def refresh_chart(self, rows):
        labels, values = build_pie_by_category(rows)
        self.chart.set_data(labels, values)

    def on_filter_changed(self):
        mode, cid = self.cmb_cat_filter.currentData()
        if mode == "UNCAT":
            self.uncategorized_filter = True
            self.category_filter = None
        elif mode == "CAT":
            self.uncategorized_filter = False
            self.category_filter = cid
        else:
            self.uncategorized_filter = False
            self.category_filter = None

        self.show_excluded = self.chk_show_excl.checkState() == Qt.Checked
        self.refresh_view()

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona CSV", "", "CSV (*.csv);;Tutti i file (*.*)")
        if not path:
            return

        preview = preview_import(self.db, path)

        if preview.duplicates:
            dlg = DuplicatesPreviewDialog(self, preview.duplicates)
            if dlg.exec() != dlg.Accepted or not dlg.proceed:
                return

        inserted = 0
        for row in preview.to_insert:
            if self.db.insert_transaction_ignore_dup(row):
                inserted += 1

        QMessageBox.information(
            self,
            "Import completato",
            f"Importati: {inserted}\nDuplicati scartati: {len(preview.duplicates)}"
        )

        self.refresh_filter_combo()
        self.refresh_view()

    def on_row_selected(self, index):
        row = self.model.get_row(index.row())
        self.current_tx_id = int(row["id"])
        self.txt_voice.setText(row["voice_raw"] or "")
        self.txt_detail.setText(row["detail_raw"] or "")

        alias = self.db.get_alias(row["voice_norm"], row["detail_norm"])
        self.txt_alias.setText(alias or "")

        cat_id = row["category_id"]
        sub_id = row["subcategory_id"]

        self.cmb_cat.blockSignals(True)
        self.cmb_cat.setCurrentIndex(self.cmb_cat.findData(int(cat_id)) if cat_id is not None else 0)
        self.cmb_cat.blockSignals(False)
        self.refresh_subcategories()

        self.cmb_sub.blockSignals(True)
        self.cmb_sub.setCurrentIndex(self.cmb_sub.findData(int(sub_id)) if sub_id is not None else 0)
        self.cmb_sub.blockSignals(False)

    def on_table_data_changed(self, topLeft, bottomRight, roles):
        if Qt.CheckStateRole not in roles:
            return
        row = self.model.get_row(topLeft.row())
        tx_id = int(row["id"])
        excluded = int(row["excluded"]) == 1
        self.db.update_excluded(tx_id, excluded)
        exclude_category_id = self._exclude_category_id()
        if exclude_category_id is not None:
            if excluded:
                self.db.update_category(tx_id, exclude_category_id, None)
            elif row["category_id"] == exclude_category_id:
                self.db.update_category(tx_id, None, None)
        self.refresh_view()

    def on_apply_category(self):
        selected_indexes = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        selected_ids = [int(self.model.get_row(idx.row())["id"]) for idx in selected_indexes]

        if not selected_ids:
            QMessageBox.information(self, "Categoria", "Seleziona prima una transazione.")
            return
        cat_id = self.cmb_cat.currentData()
        sub_id = self.cmb_sub.currentData()
        if cat_id is None:
            QMessageBox.information(self, "Categoria", "Seleziona una categoria.")
            return

        normalized_sub_id = int(sub_id) if sub_id is not None else None
        self.db.bulk_update_category(selected_ids, int(cat_id), normalized_sub_id)
        exclude_category_id = self._exclude_category_id()
        if exclude_category_id is not None:
            if int(cat_id) == exclude_category_id:
                self.db.bulk_update_excluded(selected_ids, True)
            else:
                self.db.bulk_update_excluded(selected_ids, False)

        if len(selected_ids) == 1:
            similar_rows = self.db.find_similar_transactions(selected_ids[0])
            if similar_rows:
                dlg = SimilarTransactionsDialog(self, similar_rows)
                if dlg.exec() and dlg.selected_ids:
                    self.db.bulk_update_category(dlg.selected_ids, int(cat_id), normalized_sub_id)

        self.refresh_view()

    def on_add_category(self):
        name, ok = QInputDialog.getText(self, "Nuova categoria", "Nome categoria:")
        if ok and name.strip():
            category_id = self.db.add_category(name.strip())
            self.refresh_categories()
            if category_id is not None:
                idx = self.cmb_cat.findData(int(category_id))
                if idx >= 0:
                    self.cmb_cat.setCurrentIndex(idx)
                    self.refresh_subcategories()
            self.refresh_filter_combo()
            self.refresh_view()

    def on_rename_category(self):
        cat_id = self.cmb_cat.currentData()
        if cat_id is None:
            QMessageBox.information(self, "Categoria", "Seleziona prima una categoria.")
            return

        current_name = self.cmb_cat.currentText()
        new_name, ok = QInputDialog.getText(self, "Rinomina categoria", "Nuovo nome:", text=current_name)
        if not ok or not new_name.strip():
            return

        try:
            self.db.rename_category(int(cat_id), new_name.strip())
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Categoria", "Esiste già una categoria con questo nome.")
            return

        self.refresh_categories()
        self.refresh_filter_combo()
        self.refresh_view()

    def on_add_subcategory(self):
        cat_id = self.cmb_cat.currentData()
        if cat_id is None:
            QMessageBox.information(self, "Sotto-categoria", "Seleziona prima una categoria.")
            return
        name, ok = QInputDialog.getText(self, "Nuova sotto-categoria", "Nome sotto-categoria:")
        if ok and name.strip():
            subcategory_id = self.db.add_subcategory(int(cat_id), name.strip())
            self.refresh_subcategories()
            if subcategory_id is not None:
                idx = self.cmb_sub.findData(int(subcategory_id))
                if idx >= 0:
                    self.cmb_sub.setCurrentIndex(idx)
            self.refresh_view()

    def on_rename_subcategory(self):
        sub_id = self.cmb_sub.currentData()
        if sub_id is None:
            QMessageBox.information(self, "Sotto-categoria", "Seleziona prima una sotto-categoria.")
            return

        current_name = self.cmb_sub.currentText()
        new_name, ok = QInputDialog.getText(self, "Rinomina sotto-categoria", "Nuovo nome:", text=current_name)
        if not ok or not new_name.strip():
            return

        try:
            self.db.rename_subcategory(int(sub_id), new_name.strip())
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Sotto-categoria", "Esiste già una sotto-categoria con questo nome.")
            return

        self.refresh_subcategories()
        self.refresh_view()

    def on_rename_voice(self):
        if not self.current_tx_id:
            QMessageBox.information(self, "Voce", "Seleziona prima una transazione.")
            return

        new_voice = self.txt_voice.text().strip()
        if not new_voice:
            QMessageBox.information(self, "Voce", "Inserisci una voce valida.")
            return

        voice_norm = normalize_text(new_voice)
        self.db.rename_voice(self.current_tx_id, new_voice, voice_norm)
        self.refresh_view()

    def on_save_alias(self):
        if not self.current_tx_id:
            QMessageBox.information(self, "Alias", "Seleziona prima una transazione.")
            return
        alias_value = self.txt_alias.text().strip()
        if not alias_value:
            QMessageBox.information(self, "Alias", "Inserisci un alias.")
            return

        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return
        row = self.model.get_row(idxs[0].row())

        voice_norm = row["voice_norm"]
        detail_norm = row["detail_norm"]

        self.db.upsert_alias(voice_norm, detail_norm, alias_value)

        self.refresh_view()
        QMessageBox.information(self, "Alias", "Alias salvato e applicato a tutte le voci uguali (Voce+Dettaglio).")
