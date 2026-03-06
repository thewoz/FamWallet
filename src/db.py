import sqlite3
from datetime import datetime
from typing import Optional

SCHEMA_SQL = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS subcategories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(category_id, name),
  FOREIGN KEY(category_id) REFERENCES categories(id)
);

-- Alias on (voice, detail) in normalized form
CREATE TABLE IF NOT EXISTS voice_detail_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voice_norm TEXT NOT NULL,
  detail_norm TEXT NOT NULL,
  alias_value TEXT NOT NULL,
  UNIQUE(voice_norm, detail_norm)
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date_value TEXT,                 -- YYYY-MM-DD (or original if unknown)
  voice_raw TEXT NOT NULL,         -- "Voce" (Descrizione)
  detail_raw TEXT NOT NULL,        -- "Dettaglio"
  amount TEXT NOT NULL,            -- normalized Decimal string
  voice_norm TEXT NOT NULL,
  detail_norm TEXT NOT NULL,
  amount_norm TEXT NOT NULL,       -- same as amount but kept for clarity
  excluded INTEGER NOT NULL DEFAULT 0,

  category_id INTEGER,
  subcategory_id INTEGER,

  created_at TEXT NOT NULL,

  FOREIGN KEY(category_id) REFERENCES categories(id),
  FOREIGN KEY(subcategory_id) REFERENCES subcategories(id),

  -- Duplicate definition: date + voice + detail + amount (all normalized)
  UNIQUE(date_value, voice_norm, detail_norm, amount_norm)
);

CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date_value);
CREATE INDEX IF NOT EXISTS idx_tx_cat ON transactions(category_id, subcategory_id);
CREATE INDEX IF NOT EXISTS idx_tx_excl ON transactions(excluded);
CREATE INDEX IF NOT EXISTS idx_tx_norm ON transactions(voice_norm, detail_norm);
"""

class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def now_iso(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def init_schema(self):
        cur = self.conn.cursor()
        cur.executescript(SCHEMA_SQL)
        self.conn.commit()
        self._seed_defaults()
        self._migrate_excluded_categories()

    def _seed_defaults(self):
        cur = self.conn.cursor()
        default_categories = [
            "Casa",
            "Trasporti",
            "Investimenti",
            "Banca",
            "Alimentari",
            "Svago",
            "Vestiti",
            "Bambini",
            "Regali",
        ]
        for name in default_categories:
            cur.execute("INSERT OR IGNORE INTO categories(name, active) VALUES(?, 1)", (name,))
        self.conn.commit()


    def _migrate_excluded_categories(self):
        excluded_names = ("Eliminati", "Escludi")
        placeholders = ",".join(["?"] * len(excluded_names))

        rows = self.conn.execute(
            f"SELECT id FROM categories WHERE name IN ({placeholders})",
            excluded_names
        ).fetchall()
        if not rows:
            return

        category_ids = [int(row["id"]) for row in rows]
        cat_placeholders = ",".join(["?"] * len(category_ids))

        self.conn.execute(
            f"""
            UPDATE transactions
            SET excluded=1, category_id=NULL, subcategory_id=NULL
            WHERE category_id IN ({cat_placeholders})
            """,
            category_ids
        )
        self.conn.execute(
            f"UPDATE categories SET active=0 WHERE id IN ({cat_placeholders})",
            category_ids
        )
        self.conn.commit()

    # ---------- categories ----------
    def list_categories(self):
        return self.conn.execute(
            "SELECT id, name FROM categories WHERE active=1 ORDER BY name"
        ).fetchall()

    def add_category(self, name: str):
        clean_name = name.strip()
        self.conn.execute(
            "INSERT OR IGNORE INTO categories(name, active) VALUES(?, 1)",
            (clean_name,)
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM categories WHERE name=?", (clean_name,)).fetchone()
        return int(row["id"]) if row else None

    def rename_category(self, category_id: int, new_name: str):
        self.conn.execute(
            "UPDATE categories SET name=? WHERE id=?",
            (new_name.strip(), category_id)
        )
        self.conn.commit()

    def delete_category(self, category_id: int):
        self.conn.execute(
            "UPDATE transactions SET category_id=NULL, subcategory_id=NULL WHERE category_id=?",
            (category_id,)
        )
        self.conn.execute(
            "UPDATE subcategories SET active=0 WHERE category_id=?",
            (category_id,)
        )
        self.conn.execute(
            "UPDATE categories SET active=0 WHERE id=?",
            (category_id,)
        )
        self.conn.commit()

    def list_subcategories(self, category_id: int):
        return self.conn.execute(
            "SELECT id, name FROM subcategories WHERE category_id=? AND active=1 ORDER BY name",
            (category_id,)
        ).fetchall()

    def add_subcategory(self, category_id: int, name: str):
        clean_name = name.strip()
        self.conn.execute(
            "INSERT OR IGNORE INTO subcategories(category_id, name, active) VALUES(?, ?, 1)",
            (category_id, clean_name)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM subcategories WHERE category_id=? AND name=?",
            (category_id, clean_name)
        ).fetchone()
        return int(row["id"]) if row else None

    def rename_subcategory(self, subcategory_id: int, new_name: str):
        self.conn.execute(
            "UPDATE subcategories SET name=? WHERE id=?",
            (new_name.strip(), subcategory_id)
        )
        self.conn.commit()

    def delete_subcategory(self, subcategory_id: int):
        self.conn.execute(
            "UPDATE transactions SET subcategory_id=NULL WHERE subcategory_id=?",
            (subcategory_id,)
        )
        self.conn.execute(
            "UPDATE subcategories SET active=0 WHERE id=?",
            (subcategory_id,)
        )
        self.conn.commit()

    def category_name_map(self):
        rows = self.conn.execute("SELECT id, name FROM categories WHERE active=1").fetchall()
        return {int(r["id"]): r["name"] for r in rows}

    # ---------- aliases (voice-detail) ----------
    def upsert_alias(self, voice_norm: str, detail_norm: str, alias_value: str):
        self.conn.execute(
            """
            INSERT INTO voice_detail_aliases(voice_norm, detail_norm, alias_value)
            VALUES(?, ?, ?)
            ON CONFLICT(voice_norm, detail_norm) DO UPDATE SET alias_value=excluded.alias_value
            """,
            (voice_norm, detail_norm, alias_value.strip())
        )
        self.conn.commit()

    def get_alias(self, voice_norm: str, detail_norm: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT alias_value FROM voice_detail_aliases WHERE voice_norm=? AND detail_norm=?",
            (voice_norm, detail_norm)
        ).fetchone()
        return row["alias_value"] if row else None

    def rename_voice(self, tx_id: int, voice_raw: str, voice_norm: str):
        self.conn.execute(
            "UPDATE transactions SET voice_raw=?, voice_norm=? WHERE id=?",
            (voice_raw.strip(), voice_norm, tx_id)
        )
        self.conn.commit()

    # ---------- transactions ----------
    def is_duplicate(self, date_value: str, voice_norm: str, detail_norm: str, amount_norm: str) -> bool:
        row = self.conn.execute(
            """
            SELECT id FROM transactions
            WHERE date_value=? AND voice_norm=? AND detail_norm=? AND amount_norm=?
            """,
            (date_value, voice_norm, detail_norm, amount_norm)
        ).fetchone()
        return row is not None

    def insert_transaction_ignore_dup(self, row: dict) -> bool:
        """
        Returns True if inserted, False if duplicate (ignored).
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO transactions(
              date_value, voice_raw, detail_raw, amount,
              voice_norm, detail_norm, amount_norm,
              excluded, category_id, subcategory_id, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["date_value"],
                row["voice_raw"],
                row["detail_raw"],
                row["amount"],
                row["voice_norm"],
                row["detail_norm"],
                row["amount_norm"],
                int(row.get("excluded", 0)),
                row.get("category_id"),
                row.get("subcategory_id"),
                row["created_at"],
            )
        )
        self.conn.commit()
        return cur.rowcount == 1

    def fetch_transactions(self, category_filter: Optional[int], uncategorized: bool, show_excluded: bool):
        sql = """
        SELECT
          t.id,
          t.date_value,
          t.voice_raw,
          t.detail_raw,
          t.amount,
          t.excluded,
          t.category_id,
          t.subcategory_id,
          c.name AS category_name,
          s.name AS subcategory_name,
          t.voice_norm,
          t.detail_norm
        FROM transactions t
        LEFT JOIN categories c ON c.id=t.category_id
        LEFT JOIN subcategories s ON s.id=t.subcategory_id
        WHERE 1=1
        """
        params = []

        if uncategorized:
            sql += " AND t.category_id IS NULL"
        elif category_filter is not None:
            sql += " AND t.category_id=?"
            params.append(int(category_filter))

        if show_excluded:
            sql += " AND t.excluded=1"
        else:
            sql += " AND t.excluded=0"

        sql += " ORDER BY t.date_value DESC, t.id DESC"

        return self.conn.execute(sql, params).fetchall()

    def update_excluded(self, tx_id: int, excluded: bool):
        self.conn.execute(
            """
            UPDATE transactions
            SET excluded=?,
                category_id=CASE WHEN ?=1 THEN NULL ELSE category_id END,
                subcategory_id=CASE WHEN ?=1 THEN NULL ELSE subcategory_id END
            WHERE id=?
            """,
            (1 if excluded else 0, 1 if excluded else 0, 1 if excluded else 0, tx_id)
        )
        self.conn.commit()

    def update_category(self, tx_id: int, category_id: Optional[int], subcategory_id: Optional[int]):
        self.conn.execute(
            "UPDATE transactions SET category_id=?, subcategory_id=? WHERE id=?",
            (category_id, subcategory_id, tx_id)
        )
        self.conn.commit()

    def bulk_update_category(self, tx_ids, category_id: Optional[int], subcategory_id: Optional[int]):
        ids = [int(tx_id) for tx_id in tx_ids]
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        self.conn.execute(
            f"UPDATE transactions SET category_id=?, subcategory_id=? WHERE id IN ({placeholders})",
            [category_id, subcategory_id, *ids]
        )
        self.conn.commit()

    def bulk_update_excluded(self, tx_ids, excluded: bool):
        ids = [int(tx_id) for tx_id in tx_ids]
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        self.conn.execute(
            f"""
            UPDATE transactions
            SET excluded=?,
                category_id=CASE WHEN ?=1 THEN NULL ELSE category_id END,
                subcategory_id=CASE WHEN ?=1 THEN NULL ELSE subcategory_id END
            WHERE id IN ({placeholders})
            """,
            [1 if excluded else 0, 1 if excluded else 0, 1 if excluded else 0, *ids]
        )
        self.conn.commit()

    def find_similar_transaction_ids(self, tx_id: int):
        row = self.conn.execute(
            "SELECT voice_norm, detail_norm FROM transactions WHERE id=?",
            (int(tx_id),)
        ).fetchone()
        if not row:
            return []

        results = self.conn.execute(
            "SELECT id FROM transactions WHERE voice_norm=? AND detail_norm=? AND id<>?",
            (row["voice_norm"], row["detail_norm"], int(tx_id))
        ).fetchall()
        return [int(r["id"]) for r in results]

    def find_similar_transactions(self, tx_id: int):
        row = self.conn.execute(
            "SELECT voice_norm, detail_norm FROM transactions WHERE id=?",
            (int(tx_id),)
        ).fetchone()
        if not row:
            return []

        return self.conn.execute(
            """
            SELECT id, date_value, voice_raw, detail_raw, amount
            FROM transactions
            WHERE voice_norm=? AND detail_norm=? AND id<>?
            ORDER BY date_value DESC, id DESC
            """,
            (row["voice_norm"], row["detail_norm"], int(tx_id))
        ).fetchall()
