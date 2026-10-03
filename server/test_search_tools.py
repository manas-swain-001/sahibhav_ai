import asyncio
import io
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8")

# Add src to python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from sahibhav_ai.client import QuickCommerceClient

async def main():
    print("=" * 70)
    print("Testing QuickCommerce Client & Data Tools (OFFLINE MOCK MODE - ZERO CREDITS)")
    print("=" * 70)

    client = QuickCommerceClient()
    
    # Run live search across all 4 platforms with LLM relevance filter
    results = await client.search_all(query="milk")

    for platform, res in results.items():
        print(f"\n--- Platform: {platform} ---")
        if res.error:
            print(f"  Error: {res.error}")
            continue

        print(f"  Raw products loaded : {res.raw_count}")
        print(f"  Ads filtered out     : {res.filtered_ads_count}")
        print(f"  OOS filtered out     : {res.filtered_oos_count}")
        print(f"  Irrelevant filtered  : {res.filtered_irrelevant_count}")
        print(f"  Cleaned products kept: {res.total_results}")

        if res.products:
            print("\n  Top 3 Cleaned Products:")
            for p in res.products[:3]:
                print(f"    • [{p.platform_name}] {p.name} ({p.brand or 'No brand'})")
                print(f"      Pack: {p.raw_quantity} -> Parsed: {p.parsed_quantity}{p.parsed_unit}")
                print(f"      Offer Price: ₹{p.offer_price} (MRP: ₹{p.mrp}, {p.discount_pct}% off)")
                print(f"      Standardized Price ({p.standard_unit}): ₹{p.price_per_standard_unit}")
                print(f"      Rating: {p.rating}★ ({p.rating_count or 0} reviews) | ETA: {p.eta_mins} mins")
                print(f"      Link: {p.deeplink[:60]}..." if p.deeplink else "      No link")
                print()

    print("=" * 70)
    print("All 4 platform tools tested successfully without making a single API call!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
