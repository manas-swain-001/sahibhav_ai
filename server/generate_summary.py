"""
Creates a human-readable summary of fetched products for manual review.
Groups by search query -> platform -> products (top 5 per platform to keep it manageable).
Output: server/data/products_summary.md
"""

import json
from pathlib import Path

INPUT_FILE = Path(__file__).parent / "data" / "fetched_products.json"
OUTPUT_FILE = Path(__file__).parent / "data" / "products_summary.md"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

results = data["results"]

# Group results by search query
from collections import defaultdict
query_groups = defaultdict(list)
for r in results:
    key = (r["group"], r["item"], r["search_query"])
    query_groups[key].append(r)

lines = []
lines.append("# Fetched Products Summary")
lines.append(f"**Total API calls:** {data['total_api_calls']}")
lines.append(f"**Fetch time:** {data['fetch_timestamp']}")
lines.append(f"**Location:** Lat {data['location']['lat']}, Lon {data['location']['lon']}")
lines.append("")
lines.append("---")
lines.append("")

query_num = 0
for (group, item, search_query), platform_results in query_groups.items():
    query_num += 1
    lines.append(f"## Query {query_num}: `{search_query}`")
    lines.append(f"**Group:** {group} | **Item:** {item}")
    lines.append("")

    for pr in platform_results:
        platform = pr["platform"]
        status = pr["status"]
        products = pr["products"]
        count = pr["product_count"]

        lines.append(f"### {platform} ({count} products) {'[ERROR]' if status != 'ok' else ''}")
        lines.append("")

        if not products:
            lines.append("_No products found_")
            lines.append("")
            continue

        # Show ALL products (not just top 5) so user can fully review
        lines.append("| # | Name | Brand | MRP | Offer Price | Quantity | Rating | Available |")
        lines.append("|---|------|-------|-----|-------------|----------|--------|-----------|")

        for i, p in enumerate(products, 1):
            name = p.get("name", "N/A")
            brand = p.get("brand", "-")
            mrp = p.get("mrp", "-")
            offer = p.get("offer_price", "-")
            qty = p.get("quantity", "-")
            rating = p.get("rating", "-")
            available = "Yes" if p.get("available", True) else "No"
            is_ad = " [AD]" if p.get("is_ad", False) else ""

            # Truncate long names
            if isinstance(name, str) and len(name) > 60:
                name = name[:57] + "..."

            lines.append(f"| {i}{is_ad} | {name} | {brand} | {mrp} | {offer} | {qty} | {rating} | {available} |")

        lines.append("")

    lines.append("---")
    lines.append("")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Summary written to: {OUTPUT_FILE}")
print(f"Total queries: {query_num}")
print(f"Total product rows: {sum(r['product_count'] for r in results)}")
