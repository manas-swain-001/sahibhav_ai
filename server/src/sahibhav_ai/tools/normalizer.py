from typing import Optional
from ..models import RawProduct, CleanedProduct
from .quantity_parser import parse_quantity
from .eta_parser import parse_eta
from .pricing import compute_standard_price

def normalize_product(p: RawProduct, fallback_platform_name: str = "") -> CleanedProduct:
    """
    Transforms a raw quick-commerce product into a clean, normalized, standardized CleanedProduct.
    """
    platform_name = p.platform.name if (p.platform and p.platform.name) else fallback_platform_name

    # 1. Parse Quantity
    qty_info = parse_quantity(p.quantity)

    # 2. Standardized Price
    std_unit, price_per_std = compute_standard_price(
        offer_price=p.offer_price,
        amount=qty_info.amount,
        unit=qty_info.unit
    )

    # 3. Discount Percentage
    discount_pct = 0.0
    if p.mrp > p.offer_price and p.mrp > 0:
        discount_pct = round(((p.mrp - p.offer_price) / p.mrp) * 100.0, 1)

    # 4. ETA
    eta_mins = parse_eta(p.platform.sla if p.platform else None)

    # 5. Image URL
    image_url = p.images[0] if (p.images and len(p.images) > 0) else None

    return CleanedProduct(
        id=str(p.id),
        platform_name=platform_name,
        name=p.name.strip(),
        brand=p.brand.strip() if p.brand else None,
        mrp=round(p.mrp, 2),
        offer_price=round(p.offer_price, 2),
        discount_pct=discount_pct,
        raw_quantity=p.quantity,
        parsed_quantity=qty_info.amount,
        parsed_unit=qty_info.unit,
        standard_unit=std_unit,
        price_per_standard_unit=price_per_std,
        rating=p.rating,
        rating_count=p.rating_count,
        eta_mins=eta_mins,
        deeplink=p.deeplink,
        image_url=image_url,
        is_available=p.available
    )
