from typing import List, Dict
from ..models import RawProduct
from .quantity_parser import parse_quantity

def dedupe_products(products: List[RawProduct]) -> List[RawProduct]:
    """
    Dedupes products sharing the same product ID.
    If multiple variants/entries share the same ID (common in Swiggy responses),
    keeps the smallest pack size / lowest offer price.
    """
    seen: Dict[str, RawProduct] = {}

    for p in products:
        p_id = str(p.id).strip()
        if not p_id:
            continue

        if p_id not in seen:
            seen[p_id] = p
        else:
            # If seen before, compare quantity/price and keep the smaller/cheaper pack
            existing = seen[p_id]
            qty_exist = parse_quantity(existing.quantity, product_name=existing.name).amount
            qty_curr = parse_quantity(p.quantity, product_name=p.name).amount

            # Keep smaller pack or cheaper price
            if qty_curr < qty_exist or (qty_curr == qty_exist and p.offer_price < existing.offer_price):
                seen[p_id] = p

    return list(seen.values())
