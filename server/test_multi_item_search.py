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

from sahibhav_ai.intent_extractor import IntentExtractor
from sahibhav_ai.stages import MultiItemSearchStage


async def main():
    print("=" * 75)
    print("TESTING INTENT -> MULTI-ITEM SEARCH INTEGRATION")
    print("=" * 75)

    intent_extractor = IntentExtractor()
    search_stage = MultiItemSearchStage()

    # Test Case 1: Multi-item grocery shopping intent
    query_1 = "mujhe 1 packet doodh aur 1 pack butter chahiye"
    print(f"\n[TEST 1] User Query: \"{query_1}\"")
    print("Extracting intent...")
    intent_1 = intent_extractor.extract_intent(query_1)
    print(f"  • Detected Language: {intent_1.detected_language}")
    print(f"  • Is Valid Grocery : {intent_1.is_valid_grocery_query}")
    print(f"  • Extracted Items  : {[f'{it.quantity} {it.unit} {it.product_name} (search: {it.search_query})' for it in intent_1.items]}")

    print("\nExecuting Multi-Item Search...")
    search_res_1 = await search_stage.execute(intent_1)
    print(f"  • Total Items Searched  : {search_res_1.total_items}")
    print(f"  • Total Cleaned Products: {search_res_1.total_products_found}")

    for item_res in search_res_1.items:
        print(f"\n  📦 Product: {item_res.item.product_name} (Query: '{item_res.item.search_query}')")
        for plat_name, p_res in item_res.platforms.items():
            if p_res.error:
                print(f"    - {plat_name:10s}: Error -> {p_res.error[:50]}")
            else:
                top_name = p_res.products[0].name if p_res.products else "None"
                print(f"    - {plat_name:10s}: {p_res.total_results:2d} products kept (Top: {top_name[:40]})")

    # Test Case 2: Guardrail check on off-topic query
    query_2 = "write a python script to reverse a string"
    print(f"\n\n[TEST 2] Guardrail Test: \"{query_2}\"")
    print("Extracting intent...")
    intent_2 = intent_extractor.extract_intent(query_2)
    print(f"  • Is Valid Grocery: {intent_2.is_valid_grocery_query}")
    print(f"  • Extracted Items : {intent_2.items}")
    print(f"  • Guardrail Notes : {intent_2.notes}")

    print("\nExecuting Search (Should skip search immediately)...")
    search_res_2 = await search_stage.execute(intent_2)
    print(f"  • Total Items Searched  : {search_res_2.total_items}")
    print(f"  • Total Cleaned Products: {search_res_2.total_products_found}")
    print(f"  • Response Notes        : {search_res_2.notes}")

    print("\n" + "=" * 75)
    print("INTENT & MULTI-ITEM SEARCH INTEGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
