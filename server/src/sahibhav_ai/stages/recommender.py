import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, cast

from pydantic import BaseModel, Field, SecretStr
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from ..config import GROQ_API_KEY, PRIMARY_MODEL, FALLBACK_MODEL
from ..models import (
    UserIntent,
    ItemRequirement,
    CleanedProduct,
    MultiItemSearchResult,
    CartItemPick,
    PlatformOrder,
    CartCombination,
    OptimizationResult,
    SahiBhavResponse,
)
from ..tools.eta_parser import parse_eta

# ─────────────────────────────────────────────────────────────────────────────
# LOG FILE PATH FOR MANUAL TRACE INSPECTION
# ─────────────────────────────────────────────────────────────────────────────
TRACE_LOG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "recommendation_trace.log"


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURED LLM OUTPUT SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class LLMPickDecision(BaseModel):
    item_name: str = Field(description="Name of the requested grocery item (e.g. 'Milk')")
    picked_product_id: str = Field(description="Exact ID of the chosen product from candidate list")
    platform: str = Field(description="Platform name: 'BlinkIt', 'Zepto', 'Swiggy', or 'BigBasket'")
    product_name: str = Field(description="Full product title")
    brand: Optional[str] = Field(default=None, description="Brand name of the chosen product")
    quantity: str = Field(description="Pack size/quantity string of the product (e.g. '500 ml', '1 kg')")
    offer_price: float = Field(description="Offer price of the item")
    mrp: float = Field(description="MRP of the item")
    is_exact_brand_match: bool = Field(default=True, description="True if this matches user's preferred brand, False if a suggested alternative")
    selection_reason: str = Field(description="Why this product was chosen (cheapest, fastest, best rating, brand match, etc.)")


class SinglePlatformTotal(BaseModel):
    platform: str
    items_subtotal: float
    delivery_fee: float
    grand_total: float
    has_all_items: bool = True
    missing_items: List[str] = Field(default_factory=list)


class LLMRecommendationOutput(BaseModel):
    strategy: str = Field(description="'single_platform' or 'split_2_platform'")
    winning_platforms: List[str] = Field(description="List of winning platforms e.g. ['BlinkIt'] or ['Zepto', 'Swiggy']")
    picks: List[LLMPickDecision] = Field(description="Chosen product for each requested item")
    items_subtotal: float = Field(description="Sum of all item offer prices in the winning combo")
    estimated_delivery_fees: float = Field(description="Total delivery fees for the winning combo (~Rs.25-30 per platform if under Rs.200)")
    grand_total: float = Field(description="items_subtotal + estimated_delivery_fees")
    savings_vs_highest: float = Field(description="Money saved compared to the most expensive single store")
    brand_tradeoff_notes: Optional[str] = Field(default=None, description="Detailed explanation of brand availability, alternatives, and price trade-offs")
    delivery_fee_explanation: Optional[str] = Field(default=None, description="Why single-store vs split was chosen based on delivery fee arithmetic")
    all_single_platform_estimates: List[SinglePlatformTotal] = Field(default_factory=list, description="Cost breakdown for each single store")
    natural_language_response: str = Field(description="Conversational, street-smart recommendation in the user's detected language")


# ─────────────────────────────────────────────────────────────────────────────
# MASTER RECOMMENDER SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
MASTER_RECOMMENDER_SYSTEM_PROMPT = """You are SahiBhav AI — India's smartest quick-commerce shopping optimizer across Blinkit, Zepto, Swiggy Instamart, and BigBasket.

Your job is to analyze all candidate products across platforms, identify the highest-value options, spot hidden gems, evaluate delivery fee arithmetic, and deliver a street-smart, transparent shopping recommendation.

============================================================
1. CORE OPTIMIZATION WEIGHTS (90 / 7 / 3 RULE)
============================================================
When evaluating products across platforms for each requested item:
- 90% WEIGHT — PRICE (CHEAPEST): Price is king. Pick the lowest offer price for the user's requested pack size / quantity.
- 7% WEIGHT — SPEED (QUICKEST): Favor platforms with lower delivery ETA minutes.
- 3% WEIGHT — RATINGS (QUALITY): Higher ratings win close price ties.
  * DEFAULT RATING RULE: If a product has no rating (null/None/No rating), treat its rating as 4.0★ by default.
  * HIDDEN GEMS: If you spot a newly listed product or lesser-known brand with high ratings (4.5★–5.0★) at a significantly cheaper price, prioritize it as a high-value find!

============================================================
2. STRICT CATEGORY & PRODUCT PURITY (UNIVERSAL GENERALIZATION)
============================================================
Quick-commerce search returns frequent keyword collisions. You must enforce STRICT SEMANTIC PURITY:

UNIVERSAL PURITY PRINCIPLE (APPLIES TO ALL PRODUCTS):
When a user asks for an item, pick ONLY the pure, primary form of that item.
Always ask yourself:
1. Is this the actual raw/staple product requested, or just an ingredient inside a flavored snack?
2. Is this a consumable food, or an appliance/utensil/tool?
3. Is it in the intended category (e.g., kitchen/cooking vs. pooja/cosmetics)?

ILLUSTRATIVE EXAMPLES:
- "Milk" / "Doodh" / "Khira" -> MUST be pure liquid drinking milk (pouch/bottle: toned, cow, full cream, buffalo).
  ❌ REJECT: Dairy Milk chocolate, Milk Bikis biscuits, Milkshake, Condensed milk, Milk powder, Milk cake, Milk pans/cookware.
- "Butter" / "Makkhan" -> MUST be dairy table butter (salted, unsalted, white).
  ❌ REJECT: Peanut butter, Butter cookies, Butter chicken gravy, Body butter.
- "Coffee" -> MUST be pure coffee powder/beans.
  ❌ REJECT: Coffee mugs, Coffee cake, Coffee face wash.
- "Atta" / "Flour" -> MUST be cooking wheat flour / whole wheat atta.
  ❌ REJECT: Atta noodles, Atta biscuits.
- "Banana" / "Kela" -> MUST be fresh fruit bananas.
  ❌ REJECT: Banana chips, Banana bread, Banana hair masks.
- "Ghee" -> MUST be pure desi / cow ghee.
  ❌ REJECT: Ghee diyas/wicks (pooja), Ghee roast masala paste.
- "Oil" / "Tel" -> MUST be edible cooking oil.
  ❌ REJECT: Hair oil, Massage oil, Oil dispensers/bottles.
- "Soap" -> MUST be bathing body soap.
  ❌ REJECT: Soap holders/dishes, Dishwash bars (Vim bar).

CRITICAL INSTRUCTION ON COVERAGE:
The examples above are ONLY illustrative examples. You MUST generalize and apply this exact same purity filter to EVERY single product in the catalog (spices, rice, pulses, personal care, household essentials, fruits, beverages, vegetables, cleaning items, etc.). Never pick a derivative, snack, cosmetic, or utensil when a user wants a grocery staple.

============================================================
3. BRAND MATCHING & SMART SUBSTITUTION INTELLIGENCE
============================================================
If the user specified a brand preference (e.g., "Nandini milk", "Amul butter", "Aashirvaad atta"):
1. FIRST PRIORITY: Look for that exact brand across all platforms.
2. AVAILABILITY & PRICE COMPARISON:
   - If Platform X has the exact brand at the best price -> Pick it.
   - If the exact brand is NOT available on a platform (e.g. Zepto has no Nandini), or only available in expensive bulk bundles (e.g. Swiggy only has 4-pack Rs.108):
     * Identify the best alternative brand on that platform (e.g. Amul / Mother Dairy at Rs.24).
     * Calculate the price difference.
3. CONVERSATIONAL TRADE-OFF ADVICE:
   Explain the exact situation to the user clearly in their language:
   "Aapne [Requested Brand] manga tha:
    - [Platform A] pe [Requested Brand] available nahi hai, par wahan [Alternative Brand] sirf Rs.[Price] mein hai.
    - [Platform B] pe [Requested Brand] available hai par total Rs.[Price] ban raha hai.
    - Recommendation: Agar aap [Alternative Brand] choose karte hain, toh [Platform A] se order karna Rs.[Savings] sasta padega!"

============================================================
4. SINGLE-STORE VS SPLIT-STORE COMBINATIONS (DELIVERY FEES)
============================================================
- Delivery fee assumption: ~Rs.25–Rs.30 per platform unless platform subtotal is above Rs.199 (Free Delivery).
- Splitting across 2 platforms incurs TWO delivery fees!
- Compare:
  Option A: All items from Best Single Platform (Items + 1 Delivery Fee)
  Option B: Items split across 2 Platforms (Store 1 items + Store 2 items + 2 Delivery Fees)
- ONLY recommend splitting if the grocery savings exceed the second delivery fee by at least Rs.15!
- If the extra delivery fee wipes out the savings, clearly tell the user:
  "Single platform se order karna behtar hai kyunki split karne se extra delivery fee lag jayegi."

============================================================
5. MULTILINGUAL COMMUNICATION TONE
============================================================
- Respond naturally in the user's detected language (Hindi, Hinglish, Odia, Bengali, Tamil, Telugu, Kannada, Marathi, English, etc.).
- Tone: Street-smart, helpful, honest, and price-conscious Indian shopper.
- Clearly state:
  1. Winning store(s) and why.
  2. Item-by-item breakdown (product name, pack size, price).
  3. Total items cost + delivery fee = Grand Total.
  4. Total money saved compared to the most expensive store.
  5. Any brand trade-offs or delivery fee advice.
"""


# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDER STAGE IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
class SmartRecommenderStage:
    """
    Second LLM Stage:
      - Takes all filtered candidate products across all platforms.
      - Formats them into a token-dense text representation.
      - Executes LangChain ChatGroq chain with structured output.
      - Re-hydrates winning product picks with full CleanedProduct metadata.
      - Writes complete execution traces to data/recommendation_trace.log.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.api_key = api_key or GROQ_API_KEY
        self.primary_model_name = primary_model or PRIMARY_MODEL
        self.fallback_model_name = fallback_model or FALLBACK_MODEL

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", MASTER_RECOMMENDER_SYSTEM_PROMPT),
            (
                "human",
                "User Query: \"{raw_query}\"\n"
                "Detected Language: {detected_language}\n\n"
                "CANDIDATE PRODUCTS POOL:\n"
                "{candidate_text}\n\n"
                "Evaluate all candidates according to the 90/7/3 rule, purity principle, brand preferences, "
                "and delivery fee math. Return your complete structured recommendation."
            ),
        ])

        groq_key = SecretStr(self.api_key) if self.api_key else None

        primary_llm = ChatGroq(
            model=self.primary_model_name,
            api_key=groq_key,
            temperature=0.0,
        ).with_structured_output(LLMRecommendationOutput)

        fallback_llm = ChatGroq(
            model=self.fallback_model_name,
            api_key=groq_key,
            temperature=0.0,
        ).with_structured_output(LLMRecommendationOutput)

        self.chain = self.prompt | primary_llm.with_fallbacks([fallback_llm])

    def format_candidate_pool(
        self,
        search_result: MultiItemSearchResult,
    ) -> Tuple[str, Dict[str, CleanedProduct]]:
        """
        Formats all products from search results into a compact, token-dense representation.
        Returns:
          (candidate_text, product_id_map)
        """
        lines: List[str] = []
        product_map: Dict[str, CleanedProduct] = {}

        for idx, item_res in enumerate(search_result.items, start=1):
            item = item_res.item
            brand_label = f" | Preferred Brand: {item.brand_preference}" if item.brand_preference else " | Preferred Brand: Any"
            lines.append(f"\n=== ITEM {idx}: {item.product_name} (Requested: {item.quantity} {item.unit}{brand_label}) ===")

            for plat_name, plat_res in item_res.platforms.items():
                if plat_res.error:
                    continue
                # Include up to 12 products per platform (48 products per item across 4 platforms)
                # to provide deep catalog coverage while staying comfortably within Groq's 8,000 TPM limit.
                for p in plat_res.products[:12]:
                    # Save into lookup map
                    product_map[str(p.id)] = p

                    # Build dense row
                    eta_str = f"{p.eta_mins}m" if p.eta_mins is not None else "15m"
                    rating_str = f"{p.rating}*" if p.rating is not None else "4.0* (default)"
                    rev_str = f"({p.rating_count} rev)" if p.rating_count else ""

                    disc_str = ""
                    if p.mrp > p.offer_price and p.mrp > 0:
                        disc_pct = round(((p.mrp - p.offer_price) / p.mrp) * 100)
                        disc_str = f", -{disc_pct}%"

                    brand_str = f" ({p.brand})" if p.brand else ""

                    row = (
                        f"[{p.id}] {plat_name:9s} | {p.name}{brand_str} | "
                        f"{p.quantity} | Rs.{p.offer_price} (MRP Rs.{p.mrp}{disc_str}) | "
                        f"{rating_str} {rev_str} | {eta_str}"
                    )
                    lines.append(row)

        return "\n".join(lines), product_map

    def log_trace(
        self,
        raw_query: str,
        detected_language: str,
        search_result: MultiItemSearchResult,
        candidate_text: str,
        llm_output: Optional[LLMRecommendationOutput] = None,
        error: Optional[str] = None,
    ):
        """
        Appends a detailed, human-readable trace log to server/data/recommendation_trace.log.
        """
        try:
            TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 90 + "\n")
                f.write(f"SAHI-BHAV AI RECOMMENDATION TRACE — [{timestamp}]\n")
                f.write("=" * 90 + "\n\n")

                # Stage 1: Intent & Query
                f.write("[STAGE 1: USER INPUT & EXTRACTED INTENT]\n")
                f.write(f"• Raw Query         : \"{raw_query}\"\n")
                f.write(f"• Detected Language : {detected_language}\n")
                f.write(f"• Total Items Found : {search_result.total_items}\n")
                for i, it in enumerate(search_result.items, 1):
                    pref = f" (Brand: {it.item.brand_preference})" if it.item.brand_preference else ""
                    f.write(f"  {i}. {it.item.product_name}{pref} | Qty: {it.item.quantity} {it.item.unit} | Search Query: \"{it.item.search_query}\"\n")
                f.write("\n")

                # Stage 2: Platform Search Counts
                f.write("[STAGE 2: MULTI-PLATFORM SEARCH STATS]\n")
                for it in search_result.items:
                    f.write(f"• Item: {it.item.product_name} (Query: '{it.item.search_query}')\n")
                    for plat, pres in it.platforms.items():
                        if pres.error:
                            f.write(f"  - {plat:10s}: Error -> {pres.error[:50]}\n")
                        else:
                            f.write(
                                f"  - {plat:10s}: Kept {pres.total_results:2d} products "
                                f"(Raw: {pres.raw_count:2d}, Ads: {pres.filtered_ads_count}, OOS: {pres.filtered_oos_count})\n"
                            )
                f.write(f"• Total Filtered Survivors: {search_result.total_products_found}\n\n")

                # Stage 3: Candidate Feed Sent to Second LLM
                f.write("[STAGE 3: CANDIDATE PRODUCTS PASSED TO SECOND LLM]\n")
                f.write(candidate_text.strip() + "\n\n")

                # Stage 4: LLM Decisions & Reasoning
                f.write("[STAGE 4: SECOND LLM DECISION & REASONING]\n")
                if error:
                    f.write(f"🔴 ERROR OCCURRED: {error}\n")
                elif llm_output:
                    f.write(f"• Strategy          : {llm_output.strategy}\n")
                    f.write(f"• Winning Platforms : {llm_output.winning_platforms}\n")
                    f.write(f"• Items Subtotal    : Rs.{llm_output.items_subtotal:.2f}\n")
                    f.write(f"• Delivery Fees     : Rs.{llm_output.estimated_delivery_fees:.2f}\n")
                    f.write(f"• Grand Total       : Rs.{llm_output.grand_total:.2f}\n")
                    f.write(f"• Savings vs Highest: Rs.{llm_output.savings_vs_highest:.2f}\n\n")

                    f.write("• Product Picks:\n")
                    for pick in llm_output.picks:
                        exact_str = "[Exact Brand Match]" if pick.is_exact_brand_match else "[Alternative Suggestion]"
                        f.write(
                            f"  - {pick.item_name}: [{pick.picked_product_id}] {pick.platform} | "
                            f"{pick.product_name} | Rs.{pick.offer_price:.2f} {exact_str}\n"
                            f"    Reason: {pick.selection_reason}\n"
                        )
                    f.write("\n")

                    if llm_output.brand_tradeoff_notes:
                        f.write(f"• Brand Trade-off Advice:\n  {llm_output.brand_tradeoff_notes}\n\n")

                    if llm_output.delivery_fee_explanation:
                        f.write(f"• Delivery Fee Strategy:\n  {llm_output.delivery_fee_explanation}\n\n")

                    if llm_output.all_single_platform_estimates:
                        f.write("• Single-Platform Cost Breakdown:\n")
                        for sp in llm_output.all_single_platform_estimates:
                            status = "All Items" if sp.has_all_items else f"Missing: {', '.join(sp.missing_items)}"
                            f.write(f"  - {sp.platform:10s}: Rs.{sp.grand_total:.2f} (Items: Rs.{sp.items_subtotal:.2f} + Fee: Rs.{sp.delivery_fee:.2f}) [{status}]\n")
                        f.write("\n")

                    f.write("[STAGE 5: FINAL NATURAL LANGUAGE RESPONSE]\n")
                    f.write(llm_output.natural_language_response + "\n")

                f.write("\n" + "=" * 90 + "\n\n")
        except Exception as log_err:
            print(f"[WARN] Failed to write recommendation trace: {log_err}")

    def recommend(
        self,
        raw_query: str,
        search_result: MultiItemSearchResult,
    ) -> SahiBhavResponse:
        """
        Executes the Second LLM stage:
          1. Formats all products into compact text candidate pool.
          2. Runs LLM recommender chain.
          3. Writes detailed trace log to recommendation_trace.log.
          4. Returns rich SahiBhavResponse.
        """
        if not search_result.is_valid_grocery_query or not search_result.items:
            return SahiBhavResponse(
                raw_query=raw_query,
                detected_language=search_result.detected_language,
                is_valid_grocery_query=False,
                natural_language_response=(
                    search_result.notes
                    or "Sorry, I can only help you compare grocery and household shopping prices across Blinkit, Zepto, Swiggy, and BigBasket."
                ),
            )

        # 1. Format candidate pool
        candidate_text, product_map = self.format_candidate_pool(search_result)

        # 2. Invoke LLM chain
        try:
            raw_output = self.chain.invoke({
                "raw_query": raw_query,
                "detected_language": search_result.detected_language,
                "candidate_text": candidate_text,
            })

            if isinstance(raw_output, dict):
                llm_output = LLMRecommendationOutput.model_validate(raw_output)
            else:
                llm_output = cast(LLMRecommendationOutput, raw_output)

            # 3. Write trace log
            self.log_trace(
                raw_query=raw_query,
                detected_language=search_result.detected_language,
                search_result=search_result,
                candidate_text=candidate_text,
                llm_output=llm_output,
            )

            # 4. Build CartCombination from LLM picks (re-hydrating with CleanedProduct from product_map)
            picks_by_platform: Dict[str, List[CartItemPick]] = {}
            for pick in llm_output.picks:
                full_product = product_map.get(str(pick.picked_product_id))
                if not full_product:
                    # Fallback if ID was slightly malformed
                    full_product = CleanedProduct(
                        id=pick.picked_product_id,
                        platform_name=pick.platform,
                        name=pick.product_name,
                        brand=pick.brand,
                        mrp=pick.mrp,
                        offer_price=pick.offer_price,
                        quantity=pick.quantity,
                    )

                cart_pick = CartItemPick(
                    item_name=pick.item_name,
                    search_query=pick.item_name.lower(),
                    quantity_requested=1.0,
                    unit_requested="pack",
                    platform=pick.platform,
                    product=full_product,
                    item_total_price=round(pick.offer_price, 2),
                )
                picks_by_platform.setdefault(pick.platform, []).append(cart_pick)

            orders: List[PlatformOrder] = []
            for plat, plat_picks in picks_by_platform.items():
                p_subtotal = sum(p.item_total_price for p in plat_picks)
                p_fee = 0.0 if p_subtotal >= 199.0 else 25.0
                orders.append(PlatformOrder(
                    platform=plat,
                    items=plat_picks,
                    items_subtotal=round(p_subtotal, 2),
                    delivery_fee=p_fee,
                    total_order_cost=round(p_subtotal + p_fee, 2),
                    subtotal=round(p_subtotal, 2),
                ))

            winning_combo = CartCombination(
                combo_type=llm_output.strategy,
                platforms=llm_output.winning_platforms,
                orders=orders,
                items_subtotal=llm_output.items_subtotal,
                total_delivery_fees=llm_output.estimated_delivery_fees,
                total_price=llm_output.grand_total,
                savings_vs_highest=llm_output.savings_vs_highest,
                fee_explanation=llm_output.delivery_fee_explanation,
            )

            # Build single store comparison combinations for UI tabs
            single_combos: List[CartCombination] = []
            for sp in llm_output.all_single_platform_estimates:
                single_combos.append(CartCombination(
                    combo_type="single_platform",
                    platforms=[sp.platform],
                    orders=[PlatformOrder(
                        platform=sp.platform,
                        items=[],
                        items_subtotal=sp.items_subtotal,
                        delivery_fee=sp.delivery_fee,
                        total_order_cost=sp.grand_total,
                        subtotal=sp.items_subtotal,
                    )],
                    items_subtotal=sp.items_subtotal,
                    total_delivery_fees=sp.delivery_fee,
                    total_price=sp.grand_total,
                    savings_vs_highest=max(0.0, (llm_output.grand_total if llm_output.grand_total > sp.grand_total else 0.0)),
                ))

            opt_result = OptimizationResult(
                is_valid_grocery_query=True,
                detected_language=search_result.detected_language,
                best_single_store=winning_combo if llm_output.strategy == "single_platform" else (single_combos[0] if single_combos else None),
                best_split_combo=winning_combo if llm_output.strategy == "split_2_platform" else None,
                winning_recommendation=winning_combo,
                all_single_stores=single_combos,
                notes=llm_output.brand_tradeoff_notes,
            )

            return SahiBhavResponse(
                raw_query=raw_query,
                detected_language=search_result.detected_language,
                is_valid_grocery_query=True,
                natural_language_response=llm_output.natural_language_response,
                optimization=opt_result,
                notes=llm_output.brand_tradeoff_notes,
            )

        except Exception as e:
            error_str = str(e)
            self.log_trace(
                raw_query=raw_query,
                detected_language=search_result.detected_language,
                search_result=search_result,
                candidate_text=candidate_text,
                error=error_str,
            )
            raise e
