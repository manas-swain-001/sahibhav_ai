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
from sahibhav_ai.stages import MultiItemSearchStage, ComboOptimizer


async def main():
    print("=" * 80)
    print("TESTING COMBO OPTIMIZER WITH REAL DELIVERY CHARGES & FREE DELIVERY THRESHOLD")
    print("Rule: 70% Price | 25% ETA | 5% Rating (Default 4.0★) | ₹30 Fee (< ₹200) | FREE (>= ₹200)")
    print("=" * 80)

    extractor = IntentExtractor()
    search_stage = MultiItemSearchStage()
    optimizer = ComboOptimizer()

    query = "1 packet milk aur 1 pack butter chahiye"
    print(f"\nUser Query: \"{query}\"")
    print("Step 1: Extracting user intent...")
    intent = extractor.extract_intent(query)
    print(f"  • Extracted: {[f'{it.quantity} {it.unit} {it.product_name}' for it in intent.items]}")

    print("\nStep 2: Searching all platforms...")
    search_result = await search_stage.execute(intent)
    print(f"  • Total Products Found across platforms: {search_result.total_products_found}")

    print("\nStep 3: Running Pure Python Combo Optimization...")
    opt_result = optimizer.optimize(search_result)

    print("\n" + "=" * 80)
    print("SINGLE-STORE COMPARISON (Convenience Option)")
    print("=" * 80)
    for store in opt_result.all_single_stores:
        p_name = store.platforms[0]
        order = store.orders[0]
        items_summary = ", ".join([f"{it.item_name}: {it.product.name} (₹{it.item_total_price})" for it in order.items])
        fee_label = f"₹{store.total_delivery_fees:.2f}" if store.total_delivery_fees > 0 else "FREE Delivery (>= ₹200)"
        print(f"\n🏪 [{p_name.upper()}] Items: ₹{store.items_subtotal:.2f} + Delivery: {fee_label} -> Grand Total: ₹{store.total_price:.2f}")
        print(f"   ETA: {store.max_eta_mins}m | Rating: {store.average_rating}★ | Score: {store.composite_score}")
        print(f"   Items: {items_summary}")
        if store.savings_vs_highest > 0:
            print(f"   💰 Savings: ₹{store.savings_vs_highest:.2f} cheaper than the most expensive store!")

    if opt_result.all_split_combos:
        print("\n" + "=" * 80)
        print("2-PLATFORM SPLIT COMBINATIONS (Checking if split beats single-store fees)")
        print("=" * 80)
        for combo in opt_result.all_split_combos:
            p_names = " + ".join(combo.platforms)
            print(f"\n🔀 [{p_names}] Items: ₹{combo.items_subtotal:.2f} + Delivery: ₹{combo.total_delivery_fees:.2f} -> Grand Total: ₹{combo.total_price:.2f}")
            print(f"   Max ETA: {combo.max_eta_mins}m | Score: {combo.composite_score}")
            for order in combo.orders:
                order_items = ", ".join([f"{it.item_name}: {it.product.name} (₹{it.item_total_price})" for it in order.items])
                o_fee = f"₹{order.delivery_fee:.2f}" if order.delivery_fee > 0 else "FREE"
                print(f"   • {order.platform}: Items ₹{order.items_subtotal} + Fee {o_fee} = ₹{order.total_order_cost} (ETA: {order.eta_mins}m) -> {order_items}")
            if combo.fee_explanation:
                flag = "💡" if combo.is_split_beneficial else "⚠️"
                print(f"   {flag} Analysis: {combo.fee_explanation}")

    print("\n" + "=" * 80)
    print("🏆 FINAL WINNING RECOMMENDATION (Single-Store Preference First)")
    print("=" * 80)
    winner = opt_result.winning_recommendation
    if winner:
        w_type = "Single Store (Maximum Convenience)" if winner.combo_type == "single_platform" else "2-Store Split Cart (Maximum Savings)"
        print(f"Winner Type   : {w_type}")
        print(f"Platform(s)   : {', '.join(winner.platforms)}")
        print(f"Items Subtotal: ₹{winner.items_subtotal:.2f}")
        fee_str = f"₹{winner.total_delivery_fees:.2f}" if winner.total_delivery_fees > 0 else "FREE (Orders >= ₹200)"
        print(f"Delivery Fee  : {fee_str}")
        print(f"Grand Total   : ₹{winner.total_price:.2f}")
        print(f"Delivery Time : {winner.max_eta_mins} mins")
        print(f"Score         : {winner.composite_score} / 100")
        if winner.savings_vs_highest > 0:
            print(f"Total Savings : ₹{winner.savings_vs_highest:.2f} saved!")
        print("\nBag Breakdown:")
        for o in winner.orders:
            o_fee = f"₹{o.delivery_fee:.2f}" if o.delivery_fee > 0 else "FREE"
            print(f"  👉 Platform: {o.platform} (Items: ₹{o.items_subtotal} + Delivery: {o_fee} -> Order Total: ₹{o.total_order_cost}, ETA: {o.eta_mins}m)")
            for item in o.items:
                disc = f" ({item.product.discount_pct}% off MRP ₹{item.product.mrp})" if item.product.discount_pct > 0 else ""
                print(f"     • {item.item_name}: {item.product.name} | Price: ₹{item.item_total_price}{disc}")

    print("\n" + "=" * 80)
    print("OPTIMIZER WITH DELIVERY FEES TESTED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
