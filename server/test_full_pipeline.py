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
from sahibhav_ai.stages import MultiItemSearchStage, ComboOptimizer, AIResponderStage


async def test_query(query: str, label: str):
    print("\n" + "=" * 80)
    print(f"TEST: {label}")
    print(f"Query: \"{query}\"")
    print("=" * 80)

    extractor = IntentExtractor()
    search_stage = MultiItemSearchStage()
    optimizer = ComboOptimizer()
    responder = AIResponderStage()

    # 1. Intent Extraction
    print("Step 1: Extracting intent...")
    intent = extractor.extract_intent(query)
    print(f"  • Detected Language: {intent.detected_language}")
    print(f"  • Is Valid Grocery:  {intent.is_valid_grocery_query}")
    print(f"  • Extracted Items:   {[f'{it.quantity} {it.unit} {it.product_name}' for it in intent.items]}")

    # 2. Search (Live QuickCommerce API across 4 platforms)
    print("Step 2: Live QuickCommerce Multi-Platform Search (BlinkIt, Zepto, Swiggy, BigBasket)...")
    search_result = await search_stage.execute(intent)
    print(f"  • Total Products Found: {search_result.total_products_found}")

    # 3. Combo Optimizer
    print("Step 3: Optimizing combos & delivery fees...")
    opt_result = optimizer.optimize(search_result)
    winning = opt_result.winning_recommendation
    if winning:
        print(f"  • Strategy: {winning.combo_type} on {winning.platforms}")
        print(f"  • Total: ₹{winning.total_price:.2f} (Items: ₹{winning.items_subtotal:.2f} + Fee: ₹{winning.total_delivery_fees:.2f})")
        if winning.savings_vs_highest > 0:
            print(f"  • Savings vs highest single store: ₹{winning.savings_vs_highest:.2f}")

    # 4. Multilingual AI Responder
    print("Step 4: Generating natural language response in user's language...")
    response = responder.generate_response(
        raw_query=query,
        optimization_result=opt_result,
        detected_language=intent.detected_language
    )
    print("\n--- SahiBhav AI Natural Language Response ---")
    print(response.natural_language_response)
    print("-" * 80)


async def main():
    # Test Odia query (multilingual regional language support)
    await test_query(
        query="mote 1 packet khira au butter darkar",
        label="Odia Regional Language Grocery Query"
    )


if __name__ == "__main__":
    asyncio.run(main())
