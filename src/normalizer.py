import re
from decimal import Decimal, InvalidOperation
from datetime import datetime

_SPACE_RE = re.compile(r"\s+")

def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = _SPACE_RE.sub(" ", s)
    return s

def parse_date_italian(d: str) -> str:
    """
    Returns YYYY-MM-DD if parseable, else original stripped string (so duplicates still work as string equality).
    """
    d = (d or "").strip()
    if not d or d.lower() == "non contabilizzato":
        return ""
    # try d/m/yyyy
    try:
        dt = datetime.strptime(d, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        # already ISO?
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            return d
        return d  # fallback as-is

def parse_amount_eu(a: str) -> Decimal:
    a = (a or "").strip()
    if not a:
        return Decimal("0.00")
    a = a.replace(" ", "")
    if "," in a:
        a = a.replace(".", "").replace("'", "")
        a = a.replace(",", ".")
    else:
        a = a.replace("'", "")
    try:
        d = Decimal(a)
    except InvalidOperation:
        d = Decimal("0.00")
    return d.quantize(Decimal("0.01"))
