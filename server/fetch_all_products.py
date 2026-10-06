"""
Fetch all 38 test queries across 4 platforms (Blinkit, Zepto, Swiggy, BigBasket).
Uses 2 API keys in round-robin to spread the load.
Saves raw product data to server/data/fetched_products.json
Total API calls: 38 queries × 4 platforms = 152 tokens (76 per key)
"""

import asyncio
import json
import time
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent / ".env")

# ─── Config ───────────────────────────────────────────────────────────
keys_env = os.getenv("QUICK_COMMERCE_API_KEYS", "")
API_KEYS = [k.strip() for k in keys_env.split(",") if k.strip()]
if not API_KEYS and os.getenv("QUICK_COMMERCE_API_KEY"):
    API_KEYS = [os.getenv("QUICK_COMMERCE_API_KEY", "")]

BASE_URL = os.getenv("QC_BASE_URL", "https://api.quickcommerceapi.com/v1/search")
LAT = float(os.getenv("DEFAULT_LAT", "12.9716"))
LON = float(os.getenv("DEFAULT_LON", "77.5946"))
PLATFORMS = ["BlinkIt", "Zepto", "Swiggy", "BigBasket"]

OUTPUT_FILE = Path(__file__).parent / "data" / "fetched_products.json"

# ─── All 38 Test Queries ─────────────────────────────────────────────
QUERIES = [
    # Group 1: Fresh & Breakfast Essentials (8)
    {"group": "Fresh & Breakfast", "item": "Banana (Dozen)", "query": "1 dozen banana"},
    {"group": "Fresh & Breakfast", "item": "Potato / Aloo", "query": "1kg aloo"},
    {"group": "Fresh & Breakfast", "item": "Amul Butter 100g", "query": "100g amul butter"},
    {"group": "Fresh & Breakfast", "item": "Bread + Eggs", "query": "bread"},
    {"group": "Fresh & Breakfast", "item": "Bread + Eggs", "query": "eggs"},
    {"group": "Fresh & Breakfast", "item": "Chicken Breast", "query": "500g fresh chicken breast"},
    {"group": "Fresh & Breakfast", "item": "Idli Dosa Batter", "query": "1kg idli dosa batter"},
    {"group": "Fresh & Breakfast", "item": "Kelloggs Corn Flakes", "query": "kelloggs corn flakes 500g"},
    {"group": "Fresh & Breakfast", "item": "Amul Taaza Milk", "query": "amul taaza milk 500ml"},

    # Group 2: Grocery & Kitchen Staples (6)
    {"group": "Grocery & Kitchen", "item": "Tata Salt", "query": "1kg tata salt"},
    {"group": "Grocery & Kitchen", "item": "Aashirvaad Atta 5kg", "query": "5kg aashirvaad atta"},
    {"group": "Grocery & Kitchen", "item": "Fortune Sunflower Oil", "query": "1L fortune sunflower oil"},
    {"group": "Grocery & Kitchen", "item": "Amul Cow Ghee", "query": "500ml amul cow ghee"},
    {"group": "Grocery & Kitchen", "item": "Everest Turmeric", "query": "100g everest turmeric powder"},
    {"group": "Grocery & Kitchen", "item": "Almonds / Badam", "query": "500g almonds badam"},

    # Group 3: Snacks, Drinks & Confectionery (8)
    {"group": "Snacks & Drinks", "item": "Coca-Cola Can", "query": "coca cola 300ml"},
    {"group": "Snacks & Drinks", "item": "Bisleri Water", "query": "bisleri water 1L"},
    {"group": "Snacks & Drinks", "item": "Lays Chips", "query": "lays magic masala chips"},
    {"group": "Snacks & Drinks", "item": "Good Day Cookies", "query": "good day butter cookies"},
    {"group": "Snacks & Drinks", "item": "Dairy Milk Silk", "query": "cadbury dairy milk silk"},
    {"group": "Snacks & Drinks", "item": "Amul Ice Cream", "query": "amul ice cream tub 1L"},
    {"group": "Snacks & Drinks", "item": "Maggi Noodles", "query": "maggi 4 pack noodles"},
    {"group": "Snacks & Drinks", "item": "Kissan Ketchup", "query": "kissan tomato ketchup 500g"},

    # Group 4: Beauty, Wellness & Sexual Wellness (8)
    {"group": "Beauty & Wellness", "item": "Durex Air Condoms", "query": "durex air condoms 10s"},
    {"group": "Beauty & Wellness", "item": "Durex Play Lube", "query": "durex play lube 200ml"},
    {"group": "Beauty & Wellness", "item": "Manforce Delay Spray", "query": "manforce delay spray"},
    {"group": "Beauty & Wellness", "item": "Whisper Ultra XL", "query": "whisper ultra clean XL 15 pads"},
    {"group": "Beauty & Wellness", "item": "Dettol Soap", "query": "dettol soap pack of 4"},
    {"group": "Beauty & Wellness", "item": "Head & Shoulders", "query": "head and shoulders shampoo 180ml"},
    {"group": "Beauty & Wellness", "item": "Moov Spray", "query": "moov pain relief spray 50g"},
    {"group": "Beauty & Wellness", "item": "Whey Protein", "query": "1kg whey protein powder"},

    # Group 5: Household, Electronics & Specialty (8)
    {"group": "Household & Specialty", "item": "Pampers Diapers", "query": "pampers diapers M size"},
    {"group": "Household & Specialty", "item": "Type-C Cable", "query": "type-c fast charging cable"},
    {"group": "Household & Specialty", "item": "Duracell Batteries", "query": "duracell AA batteries 4 pcs"},
    {"group": "Household & Specialty", "item": "Surf Excel Liquid", "query": "surf excel matic liquid 1L"},
    {"group": "Household & Specialty", "item": "Pedigree Dog Food", "query": "1kg pedigree dog food"},
    {"group": "Household & Specialty", "item": "Uno Cards", "query": "uno playing cards game"},
    {"group": "Household & Specialty", "item": "Cricket Lighter", "query": "cricket lighter"},
    {"group": "Household & Specialty", "item": "Cycle Agarbatti", "query": "cycle agarbatti"},
]


async def fetch_one(
    client: httpx.AsyncClient,
    api_key: str,
    query_info: dict,
    platform: str,
) -> dict:
    """Fetch products for a single query on a single platform."""
    headers = {"X-API-Key": api_key, "Accept": "application/json"}
    params = {
        "q": query_info["query"],
        "lat": str(LAT),
        "lon": str(LON),
        "platform": platform,
    }

    try:
        resp = await client.get(BASE_URL, headers=headers, params=params)
        if resp.status_code == 200:
            payload = resp.json()
            products = payload.get("data", {}).get("products", [])
            return {
                "group": query_info["group"],
                "item": query_info["item"],
                "search_query": query_info["query"],
                "platform": platform,
                "status": "ok",
                "product_count": len(products),
                "products": products,
            }
        else:
            return {
                "group": query_info["group"],
                "item": query_info["item"],
                "search_query": query_info["query"],
                "platform": platform,
                "status": f"error_{resp.status_code}",
                "product_count": 0,
                "products": [],
                "error": resp.text[:200],
            }
    except Exception as e:
        return {
            "group": query_info["group"],
            "item": query_info["item"],
            "search_query": query_info["query"],
            "platform": platform,
            "status": "exception",
            "product_count": 0,
            "products": [],
            "error": str(e),
        }


async def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_results = []
    call_count = 0
    key_index = 0
    total_calls = len(QUERIES) * len(PLATFORMS)

    print(f"Starting fetch: {len(QUERIES)} queries × {len(PLATFORMS)} platforms = {total_calls} API calls")
    print(f"Using {len(API_KEYS)} API keys in round-robin")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=20.0) as client:
        for qi, query_info in enumerate(QUERIES, 1):
            # Fetch all 4 platforms for this query concurrently
            tasks = []
            keys_used = []
            for platform in PLATFORMS:
                api_key = API_KEYS[key_index % len(API_KEYS)]
                key_index += 1
                keys_used.append(api_key[-6:])
                tasks.append(fetch_one(client, api_key, query_info, platform))

            results = await asyncio.gather(*tasks)
            all_results.extend(results)
            call_count += len(PLATFORMS)

            # Summary for this query
            counts = {r["platform"]: r["product_count"] for r in results}
            errors = [r["platform"] for r in results if r["status"] != "ok"]
            status_str = " | ".join(f"{p}: {c}" for p, c in counts.items())
            error_str = f" ERRORS: {errors}" if errors else ""

            print(f"[{qi}/{len(QUERIES)}] ({call_count}/{total_calls}) "
                  f"'{query_info['query']}' -> {status_str}{error_str}")

            # Small delay between queries to avoid rate limiting
            if qi < len(QUERIES):
                await asyncio.sleep(0.3)

    # Save results
    output_data = {
        "fetch_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_queries": len(QUERIES),
        "total_api_calls": call_count,
        "location": {"lat": LAT, "lon": LON},
        "platforms": PLATFORMS,
        "results": all_results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print("=" * 60)
    total_products = sum(r["product_count"] for r in all_results)
    ok_count = sum(1 for r in all_results if r["status"] == "ok")
    err_count = sum(1 for r in all_results if r["status"] != "ok")
    print(f"DONE! {ok_count} successful, {err_count} errors")
    print(f"Total products fetched: {total_products}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
