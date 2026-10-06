import asyncio
import io
import json
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

from sahibhav_ai.intent_extractor import IntentExtractor
from sahibhav_ai.models import (
    UserIntent,
    ItemSearchResult,
    PlatformSearchResult,
    CleanedProduct,
    MultiItemSearchResult,
    RawProduct,
)
from sahibhav_ai.tools.pre_filter import clean_and_dedupe
from sahibhav_ai.tools.eta_parser import parse_eta
from sahibhav_ai.stages.recommender import SmartRecommenderStage, TRACE_LOG_PATH


def load_local_search_result_for_query(intent: UserIntent) -> MultiItemSearchResult:
    """
    Loads real products from server/data/fetched_products.json for the extracted items.
    Uses ZERO QuickCommerce API tokens!
    """
    data_path = Path(__file__).resolve().parent / "data" / "fetched_products.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("results", [])
    item_results = []
    total_products = 0

    for item in intent.items:
        # Match against saved query or item name in fetched_products
        platforms_dict = {}
        for entry in entries:
            entry_item = entry.get("item", "").lower()
            entry_query = entry.get("search_query", "").lower()
            p_name = entry.get("platform")

            item_kw = item.product_name.lower().split()[0]
            matches = item_kw in entry_item or item.search_query.lower() in entry_query

            if matches and p_name not in platforms_dict:
                raw_list = [RawProduct(**p) for p in entry.get("products", [])]
                filtered, ads_dropped, oos_dropped = clean_and_dedupe(raw_list)

                cleaned_products = []
                for p in filtered:
                    cleaned_products.append(CleanedProduct(
                        id=str(p.id),
                        platform_name=p_name,
                        name=p.name.strip(),
                        brand=p.brand.strip() if p.brand else None,
                        mrp=round(p.mrp, 2),
                        offer_price=round(p.offer_price, 2),
                        quantity=p.quantity,
                        rating=p.rating,
                        rating_count=p.rating_count,
                        eta_mins=parse_eta(p.platform.sla if p.platform else None),
                        deeplink=p.deeplink,
                        image_url=p.images[0] if (p.images and len(p.images) > 0) else None,
                        is_available=p.available,
                    ))

                platforms_dict[p_name] = PlatformSearchResult(
                    platform=p_name,
                    query=item.search_query,
                    total_results=len(cleaned_products),
                    products=cleaned_products,
                    raw_count=len(raw_list),
                    filtered_ads_count=ads_dropped,
                    filtered_oos_count=oos_dropped,
                )
                total_products += len(cleaned_products)

        item_results.append(ItemSearchResult(
            item=item,
            platforms=platforms_dict,
            total_cleaned_products=sum(p.total_results for p in platforms_dict.values()),
        ))

    return MultiItemSearchResult(
        is_valid_grocery_query=True,
        detected_language=intent.detected_language,
        items=item_results,
        total_items=len(item_results),
        total_products_found=total_products,
        notes=intent.notes,
    )


def test_recommender(query: str):
    print("=" * 80)
    print(f"TESTING SMART RECOMMENDER PIPELINE (ZERO QC API TOKENS)")
    print(f"User Query: \"{query}\"")
    print("=" * 80)

    # 1. Intent Extractor
    print("\n[Step 1] Extracting Intent...")
    extractor = IntentExtractor()
    intent = extractor.extract_intent(query)
    print(f"  • Detected Language : {intent.detected_language}")
    print(f"  • Valid Grocery     : {intent.is_valid_grocery_query}")
    for it in intent.items:
        pref = f" (Brand: {it.brand_preference})" if it.brand_preference else ""
        print(f"  • Item: {it.product_name}{pref} | Qty: {it.quantity} {it.unit} | Search: '{it.search_query}'")

    # 2. Local Search Simulation (Using saved catalog)
    print("\n[Step 2] Loading catalog products across 4 platforms (Local mode)...")
    search_res = load_local_search_result_for_query(intent)
    print(f"  • Total Items       : {search_res.total_items}")
    print(f"  • Cleaned Survivors : {search_res.total_products_found}")

    # 3. Smart Recommender LLM
    print("\n[Step 3] Running Smart Recommender LLM (Evaluating 90/7/3, Purity, Brands, Fees)...")
    recommender = SmartRecommenderStage()
    response = asyncio.run(recommender.recommend(raw_query=query, search_result=search_res))

    print("\n" + "=" * 80)
    print("AI RECOMMENDER RESULTS")
    print("=" * 80)

    if response.optimization and response.optimization.winning_recommendation:
        rec = response.optimization.winning_recommendation
        print(f"• Strategy          : {rec.combo_type}")
        print(f"• Platforms         : {rec.platforms}")
        print(f"• Items Subtotal    : ₹{rec.items_subtotal:.2f}")
        print(f"• Delivery Fees     : ₹{rec.total_delivery_fees:.2f}")
        print(f"• Grand Total       : ₹{rec.total_price:.2f}")
        print(f"• Estimated Savings : ₹{rec.savings_vs_highest:.2f}")
        print("\n• Winning Product Picks:")
        for order in rec.orders:
            for it in order.items:
                print(f"  - [{it.product.id}] {it.platform} | {it.product.name} ({it.product.brand or 'No brand'})")
                print(f"    Pack: {it.product.quantity} | Price: ₹{it.item_total_price} | ETA: {it.product.eta_mins}m")

    print("\n• Natural Language Response:")
    print(response.natural_language_response)

    if response.notes:
        print(f"\n• Brand Trade-off Notes:\n  {response.notes}")

    print("\n" + "=" * 80)
    print(f"Trace log written to: {TRACE_LOG_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    # Test with multi-item grocery query specifying brands
    test_recommender("mujhe 1 dozen banana aur 100g amul butter chahiye")
