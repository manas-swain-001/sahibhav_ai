from typing import List, Dict, Tuple
from ..models import RawProduct


def clean_and_dedupe(
    products: List[RawProduct],
) -> Tuple[List[RawProduct], int, int]:
    """
    Lightweight pre-filter for raw API products before sending to the LLM.
    No LLM calls — just simple code cleanup.

    Steps:
      1. Drop sponsored ads (is_ad == True)
      2. Drop out-of-stock items (available == False or inventory <= 0)
      3. Deduplicate by product ID (keeps first occurrence)

    Returns:
      (cleaned_products, ads_dropped, oos_dropped)
    """
    ads_dropped = 0
    oos_dropped = 0

    survivors: List[RawProduct] = []

    for p in products:
        # Step 1: Drop Ads
        if p.is_ad:
            ads_dropped += 1
            continue

        # Step 2: Drop Out of Stock
        if not p.available or (p.inventory is not None and p.inventory <= 0):
            oos_dropped += 1
            continue

        survivors.append(p)

    # Step 3: Deduplicate by product ID (keep first occurrence)
    seen: Dict[str, RawProduct] = {}
    for p in survivors:
        p_id = str(p.id).strip()
        if not p_id:
            continue
        if p_id not in seen:
            seen[p_id] = p

    deduped = list(seen.values())

    return deduped, ads_dropped, oos_dropped
