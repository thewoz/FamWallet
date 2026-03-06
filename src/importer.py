import csv
from dataclasses import dataclass
from typing import List, Tuple
from db import DB
from normalizer import normalize_text, parse_date_italian, parse_amount_eu

RowT = Tuple[str, str, str, str]  # date, voice, detail, amount string

@dataclass
class ImportPreview:
    to_insert: List[dict]
    duplicates: List[RowT]

def _detect_delimiter(sample: str) -> str:
    # Most bank exports: ';'
    if sample.count(";") >= sample.count(","):
        return ";"
    return ","

def preview_import(db: DB, path: str) -> ImportPreview:
    # Read with tolerant encodings
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
    last_err = None

    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                delim = _detect_delimiter(sample)

                reader = csv.reader(f, delimiter=delim)
                header = None
                idx = {}

                for row in reader:
                    if not row:
                        continue
                    if header is None:
                        # locate header row
                        lowered = [c.strip().lower() for c in row]
                        if "data contabile".lower() in lowered and "descrizione".lower() in lowered and "dettaglio".lower() in lowered:
                            header = row
                            idx = {c.strip().lower(): i for i, c in enumerate(header)}
                            break

                if header is None:
                    raise ValueError("Header non trovato: atteso 'Data contabile;...;Descrizione;Dettaglio;Importo'")

                # Continue reading remaining rows
                to_insert = []
                duplicates = []

                for row in reader:
                    if not row or len(row) < len(header):
                        continue
                    date_raw = row[idx.get("data valuta", idx.get("data contabile"))] if idx.get("data valuta") is not None else row[idx["data contabile"]]
                    voice_raw = row[idx["descrizione"]]
                    detail_raw = row[idx["dettaglio"]]
                    amount_raw = row[idx["importo"]]

                    date_value = parse_date_italian(date_raw)
                    voice = (voice_raw or "").strip()
                    detail = (detail_raw or "").strip()
                    amount_dec = parse_amount_eu(amount_raw)
                    amount_str = str(amount_dec)

                    voice_norm = normalize_text(voice)
                    detail_norm = normalize_text(detail)
                    amount_norm = amount_str

                    if db.is_duplicate(date_value, voice_norm, detail_norm, amount_norm):
                        duplicates.append((date_value, voice, detail, amount_str))
                    else:
                        matched_category = db.get_category_for_voice_detail(voice_norm, detail_norm)
                        category_id = int(matched_category["category_id"]) if matched_category and matched_category["category_id"] is not None else None
                        subcategory_id = int(matched_category["subcategory_id"]) if matched_category and matched_category["subcategory_id"] is not None else None

                        to_insert.append({
                            "date_value": date_value,
                            "voice_raw": voice,
                            "detail_raw": detail,
                            "amount": amount_str,
                            "voice_norm": voice_norm,
                            "detail_norm": detail_norm,
                            "amount_norm": amount_norm,
                            "excluded": 0,
                            "category_id": category_id,
                            "subcategory_id": subcategory_id,
                            "created_at": db.now_iso(),
                        })

                return ImportPreview(to_insert=to_insert, duplicates=duplicates)

        except Exception as e:
            last_err = e
            continue

    raise last_err if last_err else RuntimeError("Impossibile leggere il CSV")
