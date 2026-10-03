import re
from typing import Optional

def parse_eta(sla_str: Optional[str]) -> Optional[int]:
    """
    Parses quick-commerce SLA/delivery time strings into integer minutes.
    Examples:
      - '12 mins' -> 12
      - '7 mins' -> 7
      - '6 mins' -> 6
      - '10-15 mins' -> 15 (upper bound for safety)
      - '30-40 min' -> 40
      - 'Next day' -> 1440
    """
    if not sla_str or not sla_str.strip():
        return None

    text = sla_str.strip().lower()

    if "next day" in text or "tomorrow" in text:
        return 1440

    # Range like '10-15 mins'
    range_match = re.search(r'(\d+)\s*-\s*(\d+)', text)
    if range_match:
        return int(range_match.group(2))

    # Single number like '12 mins'
    num_match = re.search(r'(\d+)', text)
    if num_match:
        return int(num_match.group(1))

    return None
