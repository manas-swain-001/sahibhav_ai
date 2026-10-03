import re
from datetime import datetime
from pathlib import Path
from typing import Tuple, NamedTuple, Set

# Path to audit log for unhandled / unknown quantity strings
LOG_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "unhandled_quantities.log"
_LOGGED_STRINGS: Set[str] = set()


class ParsedQuantity(NamedTuple):
    amount: float
    unit: str  # 'ml', 'g', 'piece', 'pack'
    raw: str


def _log_unhandled(raw_qty: str, reason: str = "unmatched_pattern") -> None:
    """
    Silently records unknown/unhandled quantity formats into server/data/unhandled_quantities.log
    for future offline review and parser improvements.
    Deduplicates in-memory so identical items aren't repeatedly written to disk.
    """
    cleaned = raw_qty.strip()
    if not cleaned or cleaned in _LOGGED_STRINGS:
        return

    _LOGGED_STRINGS.add(cleaned)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{reason}] {cleaned}\n")
    except Exception:
        # Never crash the user's search due to a logging failure
        pass


def parse_quantity(raw_qty: str) -> ParsedQuantity:
    """
    Parses complex Indian quick commerce quantity strings into standard (amount, unit).
    Handles formats like:
      - '500 ml', '1 ltr', '1 L', '200 ml'
      - '1 kg', '500 gm', '250 g'
      - '2 x 60 g + 60 g' -> 180 g
      - '5 x 65 ml' -> 325 ml
      - '1 ltr x 4' -> 4000 ml
      - '1 pack (475 ml or 500 ml)' -> 500 ml
      - '1 pc', '6 eggs', '1 dozen'
    """
    if not raw_qty or not raw_qty.strip():
        return ParsedQuantity(amount=1.0, unit="pack", raw=raw_qty or "")

    text = raw_qty.strip().lower()

    # Pattern: '2 x 60 g + 60 g' or 'N x M unit + P unit'
    multi_add_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*([a-z]+)\s*\+\s*(\d+(?:\.\d+)?)\s*([a-z]+)?', text)
    if multi_add_match:
        count = float(multi_add_match.group(1))
        each = float(multi_add_match.group(2))
        unit = multi_add_match.group(3)
        extra = float(multi_add_match.group(4))
        total = (count * each) + extra
        norm_unit, multiplier = _normalize_unit(unit)
        return ParsedQuantity(amount=total * multiplier, unit=norm_unit, raw=raw_qty)

    # Pattern: 'N x M unit' e.g. '5 x 65 ml'
    multi_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*([a-z]+)', text)
    if multi_match:
        count = float(multi_match.group(1))
        each = float(multi_match.group(2))
        unit = multi_match.group(3)
        total = count * each
        norm_unit, multiplier = _normalize_unit(unit)
        return ParsedQuantity(amount=total * multiplier, unit=norm_unit, raw=raw_qty)

    # Pattern: 'N unit x M' e.g. '1 ltr x 4' or '500 ml x 2'
    unit_multi_match = re.search(r'(\d+(?:\.\d+)?)\s*([a-z]+)\s*x\s*(\d+(?:\.\d+)?)', text)
    if unit_multi_match:
        each = float(unit_multi_match.group(1))
        unit = unit_multi_match.group(2)
        count = float(unit_multi_match.group(3))
        total = each * count
        norm_unit, multiplier = _normalize_unit(unit)
        return ParsedQuantity(amount=total * multiplier, unit=norm_unit, raw=raw_qty)

    # Pattern: bracketed quantities e.g. '1 pack (475 ml or 500 ml)' -> pick the max or standard amount
    bracket_match = re.search(r'\((.*?)\)', text)
    if bracket_match:
        inner = bracket_match.group(1)
        # Check for 'or' like '475 ml or 500 ml' -> take 500 ml
        if "or" in inner:
            parts = inner.split("or")
            res = parse_quantity(parts[-1].strip())
            return ParsedQuantity(amount=res.amount, unit=res.unit, raw=raw_qty)
        else:
            res = parse_quantity(inner.strip())
            if res.unit in ["ml", "g"]:
                return ParsedQuantity(amount=res.amount, unit=res.unit, raw=raw_qty)

    # Standard pattern: '<number> <unit>'
    match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', text)
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        norm_unit, multiplier = _normalize_unit(unit)
        return ParsedQuantity(amount=val * multiplier, unit=norm_unit, raw=raw_qty)

    # Check for dozen
    if "dozen" in text or "darjan" in text:
        return ParsedQuantity(amount=12.0, unit="piece", raw=raw_qty)

    # Default fallback: could not match any pattern -> log for offline review!
    _log_unhandled(raw_qty, reason="unmatched_pattern")
    return ParsedQuantity(amount=1.0, unit="pack", raw=raw_qty)


def _normalize_unit(unit: str) -> Tuple[str, float]:
    """
    Normalizes unit strings and provides unit conversion multipliers:
    e.g. ('kg', 1000.0) -> 'g', ('ltr', 1000.0) -> 'ml'
    """
    u = unit.lower().strip()
    if u in ["l", "lt", "ltr", "litre", "liter", "litres", "liters"]:
        return "ml", 1000.0
    if u in ["ml", "milliliter", "millilitre"]:
        return "ml", 1.0
    if u in ["kg", "kilo", "kilogram", "kgs"]:
        return "g", 1000.0
    if u in ["g", "gm", "gms", "gram", "grams"]:
        return "g", 1.0
    if u in ["pc", "pcs", "piece", "pieces", "unit", "units"]:
        return "piece", 1.0

    # If the unit is an unknown string (e.g. 'bunches', 'rolls', 'can'), log for offline review
    if u not in ["pack", "packs", "pouch", "pouches"]:
        _log_unhandled(unit, reason="unknown_unit")

    return "pack", 1.0
