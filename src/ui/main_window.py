from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QComboBox, QCheckBox, QSplitter, QTableView, QFormLayout,
    QLineEdit, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from db import DB
from importer import preview_import
from normalizer import normalize_text
from charts import PieChartWidget, build_pie_by_category
from ui.dialogs import DuplicatesPreviewDialog

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

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        r = self.rows[index.row()]
        c = index.column()

        if role == Qt.DisplayRole:
            if c == 0: return r["date_value"] or ""
            if c == 1:
                # alias is on (voice_norm, detail_norm)
                alias = self.db.get_alias(r["voice_norm"], r["detail_norm"])
                return alias if alias else (r["voice_raw"] or "")
            if c == 2: return r["detail_raw"] or ""
            if c == 3: return r["amount"] or ""
            if c == 4: return r["category_name"] or ""
            if c == 5: return r["subcategory_name"] or ""

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
        self.show_excluded = True

        self.setWindowTitle(f"Spese (progetto: {db.path})")

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        # Top bar
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
        self.chk_show_excl.setChecked(True)
        self.chk_show_excl.stateChanged.connect(self.on_filter_changed)
        top.addWidget(self.chk_show_excl)

        top.addStretch(1)
        self.lbl_stats = QLabel("—")
        top.addWidget(self.lbl_stats)

        root_layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        # Left: table + chart
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.clicked.connect(self.on_row_selected)
        left_layout.addWidget(self.table, 3)

        self.chart = PieChartWidget()
        left_layout.addWidget(self.chart, 2)

        splitter.addWidget(left)

        # Right: edit panel
        right = QWidget()
        form = QFormLayout(right)

        self.txt_voice = QLineEdit()
        self.txt_voice.setReadOnly(True)
        self.txt_detail = QLineEdit()
        self.txt_detail.setReadOnly(True)

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
        self.btn_add_sub = QPushButton("Nuova sotto-categoria…")
        self.btn_add_sub.clicked.connect(self.on_add_subcategory)

        self.chk_excl = QCheckBox("Escludi dal calcolo")
        self.chk_excl.stateChanged.connect(self.on_excl_changed_from_panel)

        self.btn_apply = QPushButton("Applica categoria")
        self.btn_apply.clicked.connect(self.on_apply_category)

        form.addRow("Voce:", self.txt_voice)
        form.addRow("Dettaglio:", self.txt_detail)
        form.addRow("Alias:", alias_row)
        form.addRow("Categoria:", self.cmb_cat)
        form.addRow("", self.btn_add_cat)
        form.addRow("Sotto-categoria:", self.cmb_sub)
        form.addRow("", self.btn_add_sub)
        form.addRow("", self.chk_excl)
        form.addRow("", self.btn_apply)

        splitter.addWidget(right)
        splitter.setSizes([950, 450])

        self.model = TxTableModel([], self.db)
        self.table.setModel(self.model)
        self.model.dataChanged.connect(self.on_table_data_changed)

        self.refresh_categories()
        self.refresh_filter_combo()
        self.refresh_view()

    # ---------- refresh ----------
    def refresh_categories(self):
        cats = self.db.list_categories()
        self.cmb_cat.blockSignals(True)
        self.cmb_cat.clear()
        self.cmb_cat.addItem("—", None)
        for c in cats:
            self.cmb_cat.addItem(c["name"], int(c["id"]))
        self.cmb_cat.blockSignals(False)
        self.refresh_subcategories()

    def refresh_subcategories(self):
        cat_id = self.cmb_cat.currentData()
        self.cmb_sub.blockSignals(True)
        self.cmb_sub.clear()
        self.cmb_sub.addItem("—", None)
        if cat_id is not None:
            subs = self.db.list_subcategories(int(cat_id))
            for s in subs:
                self.cmb_sub.addItem(s["name"], int(s["id"]))
        self.cmb_sub.blockSignals(False)

    def refresh_filter_combo(self):
        # Keep current selection if possible
        prev = self.cmb_cat_filter.currentData()
        self.cmb_cat_filter.blockSignals(True)
        self.cmb_cat_filter.clear()
        self.cmb_cat_filter.addItem("Tutte le spese", ("ALL", None))
        self.cmb_cat_filter.addItem("Senza categoria", ("UNCAT", None))
        for c in self.db.list_categories():
            self.cmb_cat_filter.addItem(f"Solo: {c['name']}", ("CAT", int(c["id"])))
        self.cmb_cat_filter.blockSignals(False)

        # restore selection
        idx = -1
        for i in range(self.cmb_cat_filter.count()):
            if self.cmb_cat_filter.itemData(i) == prev:
                idx = i
                break
        self.cmb_cat_filter.setCurrentIndex(idx if idx >= 0 else 0)

    def refresh_view(self):
        rows = self.db.fetch_transactions(
            category_filter=self.category_filter,
            uncategorized=self.uncategorized_filter,
            show_excluded=self.show_excluded,
        )
        self.model.set_rows(rows)
        self.table.resizeColumnsToContents()
        self.refresh_stats(rows)
        self.refresh_chart(rows)

    def refresh_stats(self, rows):
        total = len(rows)
        excl = sum(1 for r in rows if int(r["excluded"]) == 1)
        unc = sum(1 for r in rows if r["category_id"] is None and int(r["excluded"]) == 0)
        self.lbl_stats.setText(f"Movimenti: {total} — Esclusi: {excl} — Senza categoria: {unc}")

    def refresh_chart(self, rows):
        labels, values = build_pie_by_category(rows)
        self.chart.set_data(labels, values)

    # ---------- events ----------
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

        self.show_excluded = (self.chk_show_excl.checkState() == Qt.Checked)
        self.refresh_view()

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona CSV", "", "CSV (*.csv);;Tutti i file (*.*)")
        if not path:
            return

        preview = preview_import(self.db, path)

        # Show duplicates before discarding
        if preview.duplicates:
            dlg = DuplicatesPreviewDialog(self, preview.duplicates)
            if dlg.exec() != dlg.Accepted or not dlg.proceed:
                return  # cancel import

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

        # show current alias (if any)
        alias = self.db.get_alias(row["voice_norm"], row["detail_norm"])
        self.txt_alias.setText(alias or "")

        # excluded checkbox
        self.chk_excl.blockSignals(True)
        self.chk_excl.setChecked(int(row["excluded"]) == 1)
        self.chk_excl.blockSignals(False)

        # category combo
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
        self.refresh_view()

    def on_excl_changed_from_panel(self):
        if not self.current_tx_id:
            return
        excluded = self.chk_excl.checkState() == Qt.Checked
        self.db.update_excluded(self.current_tx_id, excluded)
        self.refresh_view()

    def on_apply_category(self):
        if not self.current_tx_id:
            QMessageBox.information(self, "Categoria", "Seleziona prima una transazione.")
            return
        cat_id = self.cmb_cat.currentData()
        sub_id = self.cmb_sub.currentData()
        if cat_id is None:
            QMessageBox.information(self, "Categoria", "Seleziona una categoria.")
            return
        self.db.update_category(self.current_tx_id, int(cat_id), int(sub_id) if sub_id is not None else None)
        self.refresh_view()

    def on_add_category(self):
        name, ok = QInputDialog.getText(self, "Nuova categoria", "Nome categoria:")
        if ok and name.strip():
            self.db.add_category(name.strip())
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
            self.db.add_subcategory(int(cat_id), name.strip())
            # IMPORTANT: refresh and keep selection
            self.refresh_subcategories()
            self.refresh_view()

    def on_save_alias(self):
        if not self.current_tx_id:
            QMessageBox.information(self, "Alias", "Seleziona prima una transazione.")
            return
        alias_value = self.txt_alias.text().strip()
        if not alias_value:
            QMessageBox.information(self, "Alias", "Inserisci un alias.")
            return

        # Need norms for current row
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return
        row = self.model.get_row(idxs[0].row())

        voice_norm = row["voice_norm"]
        detail_norm = row["detail_norm"]

        self.db.upsert_alias(voice_norm, detail_norm, alias_value)

        # Alias is applied automatically on display for all matching (voice_norm, detail_norm)
        self.refresh_view()
        QMessageBox.information(self, "Alias", "Alias salvato e applicato a tutte le voci uguali (Voce+Dettaglio).")
