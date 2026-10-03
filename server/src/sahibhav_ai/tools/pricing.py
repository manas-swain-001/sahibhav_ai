from typing import Tuple

def compute_standard_price(
    offer_price: float,
    amount: float,
    unit: str
) -> Tuple[str, float]:
    """
    Computes a standardized reference price so products of different pack sizes
    can be compared fairly (apples to apples).

    Returns:
      (standard_unit_name, price_per_standard_unit)

    Examples:
      - Milk 1000ml for ₹54 -> ('500ml', 27.0)
      - Milk 500ml for ₹27  -> ('500ml', 27.0)
      - Atta 5000g for ₹240 -> ('1kg', 48.0)
      - Atta 1000g for ₹52  -> ('1kg', 52.0)
      - Eggs 6 pcs for ₹48  -> ('1piece', 8.0)
    """
    if offer_price <= 0 or amount <= 0:
        return unit, round(offer_price, 2)

    u = unit.lower().strip()

    if u == "ml":
        # Standardize liquids to 500ml
        standard_unit = "500ml"
        price_per_std = (offer_price / amount) * 500.0
        return standard_unit, round(price_per_std, 2)

    elif u == "g":
        # Standardize solids to 1kg (1000g)
        standard_unit = "1kg"
        price_per_std = (offer_price / amount) * 1000.0
        return standard_unit, round(price_per_std, 2)

    elif u == "piece":
        # Standardize piece items to single piece
        standard_unit = "1piece"
        price_per_std = offer_price / amount
        return standard_unit, round(price_per_std, 2)

    else:
        # Generic pack
        standard_unit = "pack"
        price_per_std = offer_price / amount
        return standard_unit, round(price_per_std, 2)
