import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FIXTURES_DIR = Path("data/fixtures")

def inspect_category(category: str, limit: int = 25):
    cat_dir = FIXTURES_DIR / category
    platforms = ["blinkit", "zepto", "swiggy", "bigbasket"]
    
    print("=" * 80)
    print(f"INVESTIGATION REPORT FOR CATEGORY: '{category.upper()}' (Bangalore)")
    print("=" * 80)

    for p in platforms:
        file_path = cat_dir / f"{p}.json"
        if not file_path.exists():
            print(f"Missing file: {file_path}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        products = data.get("data", {}).get("products", [])
        ads = [x for x in products if x.get("is_ad")]
        oos = [x for x in products if not x.get("available") or (x.get("inventory") is not None and x.get("inventory") <= 0)]

        print(f"\n--- Platform: {p.upper()} (Total items: {len(products)} | Ads: {len(ads)} | OOS: {len(oos)}) ---")
        items_to_show = products if limit == 0 else products[:limit]
        for i, prod in enumerate(items_to_show, 1):
            name = prod.get("name", "")
            brand = prod.get("brand") or "No Brand"
            qty = prod.get("quantity", "")
            price = prod.get("offer_price", 0)
            mrp = prod.get("mrp", 0)
            is_ad = prod.get("is_ad", False)
            avail = prod.get("available", True)
            
            flag = ""
            if is_ad:
                flag = "[AD] "
            if not avail:
                flag += "[OOS] "

            print(f" {flag}{i:2d}. {name} ({brand}) | Pack: {qty} | Rs.{price} (MRP: Rs.{mrp})")

if __name__ == "__main__":
    cat = sys.argv[1] if len(sys.argv) > 1 else "atta"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    inspect_category(cat, limit)
