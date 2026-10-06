import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, cast

from pydantic import BaseModel, Field, SecretStr
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from ..config import (
    GROQ_API_KEY_1,
    GROQ_API_KEY_2,
    GROQ_API_KEY,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
)
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

logger = logging.getLogger("sahibhav_ai.recommender")

# ─────────────────────────────────────────────────────────────────────────────
# LOG FILE PATH FOR MANUAL TRACE INSPECTION
# ─────────────────────────────────────────────────────────────────────────────
TRACE_LOG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "recommendation_trace.log"


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURED WORKER OUTPUT SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
class WorkerPick(BaseModel):
    item_name: str = Field(description="Name of requested grocery item")
    picked_product_id: str = Field(description="Exact ID of chosen product")
    platform: str = Field(description="Platform name: BlinkIt, Zepto, Swiggy, or BigBasket")
    product_name: str = Field(description="Product title")
    brand: Optional[str] = Field(default=None, description="Brand name")
    quantity: str = Field(description="Pack size")
    offer_price: float = Field(description="Offer price")
    mrp: float = Field(description="MRP")
    is_exact_brand_match: bool = Field(default=True)
    selection_reason: str = Field(description="Why this product was chosen")


class WorkerStoreEstimate(BaseModel):
    platform: str
    items_subtotal: float
    delivery_fee: float
    grand_total: float
    has_all_items: bool = True
    missing_items: List[str] = Field(default_factory=list)


class WorkerEvaluationOutput(BaseModel):
    evaluated_platforms: List[str]
    best_picks: List[WorkerPick] = Field(description="Best product picked per requested item across these platforms")
    single_store_estimates: List[WorkerStoreEstimate] = Field(description="Estimated cost for each single store evaluated")
    notes: Optional[str] = Field(default=None, description="Observations on brand availability or prices")


# ─────────────────────────────────────────────────────────────────────────────
# WORKER SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
WORKER_SYSTEM_PROMPT = """You are SahiBhav AI's Quick-Commerce Evaluator analyzing candidate products for a specific subset of stores.

CRITICAL RULES FOR YOUR ASSIGNED PLATFORMS:
1. SINGLE PLATFORM POLICY:
   - SahiBhav AI NEVER splits orders across multiple stores. Each store must be evaluated as an independent single-platform cart.
2. 90/7/3 RULE:
   - 90% Price: Pick lowest offer price matching user's requested pack size / quantity.
   - 7% Speed: Favor lower delivery ETA minutes.
   - 3% Rating: Treat unrated items as 4.0★. Prioritize 4.5+★ hidden gems if significantly cheaper.
3. STRICT STAPLE PURITY:
   - Pick ONLY the pure requested grocery staple (pure milk, table butter, wheat atta, edible oil, fresh fruits).
   - REJECT derivative snacks, cosmetics, utensils, cookies, chocolates, and pooja items.
4. BRAND MATCHING & SMART SUBSTITUTION:
   - If user specified a brand (e.g. 'Omfed', 'Amul', 'Aashirvaad'), prioritize products of that brand.
   - CRITICAL SUBSTITUTION RULE: If a store does NOT carry the user's requested brand, DO NOT REJECT OR MARK THE ITEM MISSING! Instead, pick the BEST ALTERNATIVE staple product available on that store in that category (e.g., Amul or Mother Dairy milk if Omfed is unavailable, Pragati or Mother Dairy curd if Omfed curd is unavailable). Mark is_exact_brand_match=False and explain the substitution.
   - An item is only missing from a store if the store has ZERO products in that grocery category.
5. STORE TOTALS & DELIVERY FEES:
   - Calculate items subtotal for each store using the chosen products (exact or substitute).
   - Delivery fee rule:
     • If subtotal >= Rs.200: delivery_fee = Rs.0 (FREE)
     • If 0 < subtotal < Rs.200: delivery_fee = Rs.25
     • If subtotal == 0: delivery_fee = Rs.0 (NEVER charge Rs.25 on Rs.0 items!)
   - Grand total = subtotal + delivery fee.
"""


# ─────────────────────────────────────────────────────────────────────────────
# SMART RECOMMENDER STAGE WITH DUAL-GROQ PARALLEL WORKERS
# ─────────────────────────────────────────────────────────────────────────────
class SmartRecommenderStage:
    """
    Parallel Dual-Worker Recommender Stage:
      - Worker 1 (GROQ_API_KEY_1): Evaluates BlinkIt & Zepto products.
      - Worker 2 (GROQ_API_KEY_2): Evaluates Swiggy & BigBasket products.
      - Runs concurrently with asyncio.gather() to evaluate ALL products without hitting the 8,000 TPM limit.
      - Final Synthesizer calculates cross-store delivery fees (single store vs split) and localized recommendation.
    """

    def __init__(
        self,
        api_key_1: Optional[str] = None,
        api_key_2: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.key_1 = api_key_1 or GROQ_API_KEY_1 or GROQ_API_KEY
        self.key_2 = api_key_2 or GROQ_API_KEY_2 or self.key_1
        self.primary_model_name = primary_model or PRIMARY_MODEL
        self.fallback_model_name = fallback_model or FALLBACK_MODEL

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", WORKER_SYSTEM_PROMPT),
            (
                "human",
                "User Query: \"{raw_query}\"\n"
                "Detected Language: {detected_language}\n"
                "Assigned Platforms: {assigned_platforms}\n\n"
                "CANDIDATE PRODUCTS:\n"
                "{candidate_text}\n\n"
                "Evaluate all candidates for your assigned platforms. Return your structured picks and store estimates."
            ),
        ])

        # Worker 1 LLM (Key 1)
        groq_key_1 = SecretStr(self.key_1) if self.key_1 else None
        p_llm_1 = ChatGroq(model=self.primary_model_name, api_key=groq_key_1, temperature=0.0).with_structured_output(WorkerEvaluationOutput)
        f_llm_1 = ChatGroq(model=self.fallback_model_name, api_key=groq_key_1, temperature=0.0).with_structured_output(WorkerEvaluationOutput)
        self.worker_1_chain = self.prompt | p_llm_1.with_fallbacks([f_llm_1])

        # Worker 2 LLM (Key 2)
        groq_key_2 = SecretStr(self.key_2) if self.key_2 else None
        p_llm_2 = ChatGroq(model=self.primary_model_name, api_key=groq_key_2, temperature=0.0).with_structured_output(WorkerEvaluationOutput)
        f_llm_2 = ChatGroq(model=self.fallback_model_name, api_key=groq_key_2, temperature=0.0).with_structured_output(WorkerEvaluationOutput)
        self.worker_2_chain = self.prompt | p_llm_2.with_fallbacks([f_llm_2])

    def format_candidate_pool_for_platforms(
        self,
        search_result: MultiItemSearchResult,
        target_platforms: List[str],
        max_per_platform: int = 8,
    ) -> Tuple[str, Dict[str, CleanedProduct]]:
        """
        Formats products for the assigned platforms into compact text.
        Includes all genuine products up to max_per_platform (default 8) per store per item.
        """
        lines: List[str] = []
        product_map: Dict[str, CleanedProduct] = {}

        for idx, item_res in enumerate(search_result.items, start=1):
            item = item_res.item
            brand_label = f" | Brand: {item.brand_preference}" if item.brand_preference else ""
            lines.append(f"\nITEM {idx}: {item.product_name} ({item.quantity} {item.unit}{brand_label})")

            for plat_name in target_platforms:
                plat_res = item_res.platforms.get(plat_name)
                if not plat_res or plat_res.error or not plat_res.products:
                    continue

                for p in plat_res.products[:max_per_platform]:
                    product_map[str(p.id)] = p

                    eta_str = f"{p.eta_mins}m" if p.eta_mins is not None else "15m"
                    rating_str = f"{p.rating}*" if p.rating is not None else "4.0*"
                    brand_str = f" ({p.brand})" if p.brand else ""

                    row = (
                        f"[{p.id}] {plat_name} | {p.name}{brand_str} | "
                        f"{p.quantity} | Rs.{p.offer_price} (MRP Rs.{p.mrp}) | "
                        f"{rating_str} | {eta_str}"
                    )
                    lines.append(row)

        return "\n".join(lines), product_map

    def _fallback_evaluate_platforms(
        self,
        search_result: MultiItemSearchResult,
        target_platforms: List[str],
        product_map: Dict[str, CleanedProduct],
    ) -> WorkerEvaluationOutput:
        """
        Deterministic rule-based evaluator for a platform subset in case a worker LLM fails.
        """
        best_picks: List[WorkerPick] = []
        store_picks: Dict[str, Dict[str, CleanedProduct]] = {p: {} for p in target_platforms}

        for item_res in search_result.items:
            item = item_res.item
            pref_brand = (item.brand_preference or "").lower().strip()
            item_candidates: List[Tuple[float, CleanedProduct, str]] = []

            for plat_name in target_platforms:
                plat_res = item_res.platforms.get(plat_name)
                if not plat_res or plat_res.error or not plat_res.products:
                    continue

                best_p: Optional[CleanedProduct] = None
                best_score = -1.0

                for p in plat_res.products:
                    is_brand_match = bool(pref_brand and (pref_brand in (p.brand or "").lower() or pref_brand in p.name.lower()))
                    brand_bonus = 25.0 if is_brand_match else 0.0
                    price_score = 90.0 * (100.0 / max(10.0, p.offer_price))
                    eta_score = 7.0 * (15.0 / max(5.0, (p.eta_mins or 15.0)))
                    rating_score = 3.0 * ((p.rating or 4.0) / 5.0)

                    score = brand_bonus + price_score + eta_score + rating_score
                    if score > best_score:
                        best_score = score
                        best_p = p

                if best_p:
                    store_picks[plat_name][item.product_name] = best_p
                    item_candidates.append((best_score, best_p, plat_name))

            if item_candidates:
                item_candidates.sort(key=lambda x: x[0], reverse=True)
                _, top_p, top_plat = item_candidates[0]
                is_bm = bool(pref_brand and (pref_brand in (top_p.brand or "").lower() or pref_brand in top_p.name.lower()))
                best_picks.append(WorkerPick(
                    item_name=item.product_name,
                    picked_product_id=str(top_p.id),
                    platform=top_plat,
                    product_name=top_p.name,
                    brand=top_p.brand,
                    quantity=top_p.quantity,
                    offer_price=top_p.offer_price,
                    mrp=top_p.mrp,
                    is_exact_brand_match=is_bm,
                    selection_reason="Optimal 90/7/3 score",
                ))

        # Store estimates
        estimates: List[WorkerStoreEstimate] = []
        for plat in target_platforms:
            items_dict = store_picks[plat]
            has_all = len(items_dict) == len(search_result.items)
            missing = [it.item.product_name for it in search_result.items if it.item.product_name not in items_dict]
            subtotal = sum(p.offer_price for p in items_dict.values())
            fee = 0.0 if subtotal >= 199.0 else (25.0 if subtotal > 0.0 else 0.0)
            grand = round(subtotal + fee, 2) if subtotal > 0.0 else 0.0
            estimates.append(WorkerStoreEstimate(
                platform=plat,
                items_subtotal=round(subtotal, 2),
                delivery_fee=fee,
                grand_total=round(grand, 2),
                has_all_items=has_all,
                missing_items=missing,
            ))

        return WorkerEvaluationOutput(
            evaluated_platforms=target_platforms,
            best_picks=best_picks,
            single_store_estimates=estimates,
            notes="Deterministic rule-based evaluation",
        )

    async def _run_worker(
        self,
        worker_id: str,
        chain: Any,
        raw_query: str,
        detected_language: str,
        assigned_platforms: List[str],
        candidate_text: str,
        product_map: Dict[str, CleanedProduct],
        search_result: MultiItemSearchResult,
    ) -> WorkerEvaluationOutput:
        """
        Executes a single worker chain asynchronously with automatic fallback.
        """
        try:
            raw_output = await chain.ainvoke({
                "raw_query": raw_query,
                "detected_language": detected_language,
                "assigned_platforms": ", ".join(assigned_platforms),
                "candidate_text": candidate_text,
            })
            if isinstance(raw_output, dict):
                return WorkerEvaluationOutput.model_validate(raw_output)
            return cast(WorkerEvaluationOutput, raw_output)
        except Exception as e:
            logger.warning(f"Worker {worker_id} ({assigned_platforms}) LLM call failed: {e}. Executing fallback evaluator.")
            return self._fallback_evaluate_platforms(search_result, assigned_platforms, product_map)

    def _build_all_single_store_combos(
        self,
        search_result: MultiItemSearchResult,
        worker_picks: List[WorkerPick],
    ) -> List[CartCombination]:
        """
        Builds complete single-store carts for BlinkIt, Zepto, Swiggy, and BigBasket.
        For each store:
          - If user preferred a brand and the store carries it, picks that brand.
          - If the store lacks the preferred brand, automatically selects the best substitute
            staple product on that store matching category & pack size.
          - Computes accurate items subtotal, delivery fee (0 if >= 199, else 25; 0 if subtotal == 0),
            and grand total.
          - Returns only valid stores with items_subtotal > 0.
        """
        combos: List[CartCombination] = []
        platforms = ["BlinkIt", "Zepto", "Swiggy", "BigBasket"]

        junk_words = {
            "biscuit", "biscuits", "cookie", "cookies", "rusk", "chocolate", "chocolates",
            "chips", "namkeen", "shampoo", "soap", "toothpaste", "pooja", "agarbatti",
            "cleaner", "diaper", "ice cream", "cake", "cream roll"
        }

        # Map worker picks for fast lookup: (platform, item_name) -> WorkerPick
        worker_pick_map: Dict[Tuple[str, str], WorkerPick] = {
            (p.platform.lower(), p.item_name.lower()): p for p in worker_picks
        }

        for plat in platforms:
            store_cart_picks: List[CartItemPick] = []
            missing_items: List[str] = []

            for item_res in search_result.items:
                item = item_res.item
                it_name = item.product_name
                pref_brand = (item.brand_preference or "").lower().strip()
                plat_res = item_res.platforms.get(plat)
                candidates = plat_res.products if (plat_res and not plat_res.error and plat_res.products) else []

                chosen_prod: Optional[CleanedProduct] = None
                is_exact_brand = False

                # 1. Check if worker LLM picked a product for this exact store
                w_pick = worker_pick_map.get((plat.lower(), it_name.lower()))
                if w_pick and candidates:
                    match_in_cand = next((c for c in candidates if str(c.id) == str(w_pick.picked_product_id)), None)
                    if match_in_cand:
                        chosen_prod = match_in_cand
                        is_exact_brand = w_pick.is_exact_brand_match

                # 2. If not picked by worker, deterministic scoring across candidates
                if not chosen_prod and candidates:
                    scored_candidates: List[Tuple[float, CleanedProduct, bool]] = []
                    for c in candidates:
                        c_title_lower = c.name.lower()
                        c_brand_lower = (c.brand or "").lower()

                        # Purity filter: skip junk/unrelated items for pure staples
                        is_junk = any(jw in c_title_lower for jw in junk_words)
                        if is_junk and not any(jw in it_name.lower() for jw in junk_words):
                            continue

                        # Brand matching
                        c_is_brand = bool(pref_brand and (pref_brand in c_brand_lower or pref_brand in c_title_lower))
                        brand_bonus = 45.0 if c_is_brand else 0.0

                        # Price score (90%)
                        price_score = 90.0 * (100.0 / max(10.0, c.offer_price))
                        # ETA score (7%)
                        eta_val = c.eta_mins or 15
                        eta_score = 7.0 * (15.0 / max(5.0, eta_val))
                        # Rating score (3%)
                        rating_score = 3.0 * ((c.rating or 4.0) / 5.0)

                        total_score = brand_bonus + price_score + eta_score + rating_score
                        scored_candidates.append((total_score, c, c_is_brand))

                    if scored_candidates:
                        scored_candidates.sort(key=lambda x: x[0], reverse=True)
                        _, chosen_prod, is_exact_brand = scored_candidates[0]

                if chosen_prod:
                    store_cart_picks.append(CartItemPick(
                        item_name=it_name,
                        search_query=item.search_query,
                        quantity_requested=item.quantity,
                        unit_requested=item.unit,
                        platform=plat,
                        product=chosen_prod,
                        item_total_price=round(chosen_prod.offer_price, 2),
                    ))
                else:
                    missing_items.append(it_name)

            # Only include stores that have products and subtotal > 0
            if store_cart_picks and sum(cp.item_total_price for cp in store_cart_picks) > 0:
                subtotal = round(sum(cp.item_total_price for cp in store_cart_picks), 2)
                # Delivery fee rule: orders >= Rs.199 free, < 199 fee Rs.25, empty Rs.0
                fee = 0.0 if subtotal >= 199.0 else 25.0
                grand_total = round(subtotal + fee, 2)
                max_eta = max((cp.product.eta_mins or 15 for cp in store_cart_picks), default=15)

                has_all = len(missing_items) == 0 and len(store_cart_picks) == len(search_result.items)
                fee_desc = (
                    f"Complete order from {plat}. Delivery: {'FREE' if fee == 0 else f'₹{fee:.0f}'}."
                    if has_all
                    else f"Order from {plat} (Missing items: {', '.join(missing_items)})."
                )

                order = PlatformOrder(
                    platform=plat,
                    items=store_cart_picks,
                    items_subtotal=subtotal,
                    delivery_fee=fee,
                    total_order_cost=grand_total,
                    subtotal=subtotal,
                    eta_mins=max_eta,
                )

                combos.append(CartCombination(
                    combo_type="single_platform",
                    platforms=[plat],
                    orders=[order],
                    items_subtotal=subtotal,
                    total_delivery_fees=fee,
                    total_price=grand_total,
                    max_eta_mins=max_eta,
                    average_rating=round(sum((cp.product.rating or 4.0) for cp in store_cart_picks) / len(store_cart_picks), 1),
                    fee_explanation=fee_desc,
                ))

        return combos

    def log_trace(
        self,
        raw_query: str,
        detected_language: str,
        search_result: MultiItemSearchResult,
        worker_1_out: WorkerEvaluationOutput,
        worker_2_out: WorkerEvaluationOutput,
        winning_combo: CartCombination,
        natural_language_response: str,
    ):
        """
        Appends a complete, detailed trace log showing all candidate products from the catalog,
        both worker evaluations, and the final synthesis for manual inspection and audit.
        """
        try:
            TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 90 + "\n")
                f.write(f"SAHI-BHAV AI DUAL-WORKER AUDIT TRACE [KEY 1 & KEY 2] — [{timestamp}]\n")
                f.write("=" * 90 + "\n\n")

                # STAGE 1: INTENT
                f.write("[STAGE 1: USER INPUT & EXTRACTED INTENT]\n")
                f.write(f"• Raw Query         : \"{raw_query}\"\n")
                f.write(f"• Detected Language : {detected_language}\n")
                f.write(f"• Total Items Found : {search_result.total_items}\n")
                for i, it in enumerate(search_result.items, 1):
                    pref = f" (Brand Preference: {it.item.brand_preference})" if it.item.brand_preference else ""
                    f.write(f"  {i}. {it.item.product_name}{pref} | Qty: {it.item.quantity} {it.item.unit} | Search Query: \"{it.item.search_query}\"\n")
                f.write("\n")

                # STAGE 2: ALL CANDIDATE PRODUCTS FROM LIVE SEARCH
                f.write("[STAGE 2: ALL CANDIDATE PRODUCTS IN LIVE CATALOG (FOR MANUAL AUDIT)]\n")
                f.write(f"• Total Products Filtered & Available: {search_result.total_products_found}\n\n")
                for i, it in enumerate(search_result.items, 1):
                    pref = f" (Brand: {it.item.brand_preference})" if it.item.brand_preference else ""
                    f.write("━" * 80 + "\n")
                    f.write(f"ITEM #{i}: {it.item.product_name} | Requested: {it.item.quantity} {it.item.unit}{pref} | Query: \"{it.item.search_query}\"\n")
                    f.write("━" * 80 + "\n")

                    for plat_name in ["BlinkIt", "Zepto", "Swiggy", "BigBasket"]:
                        plat_res = it.platforms.get(plat_name)
                        if not plat_res:
                            f.write(f"  [{plat_name}] Not queried\n")
                            continue
                        if plat_res.error:
                            f.write(f"  [{plat_name}] Error: {plat_res.error}\n")
                            continue
                        if not plat_res.products:
                            f.write(f"  [{plat_name}] 0 products found / out of stock in this pincode\n")
                            continue

                        f.write(f"  [{plat_name}] ({len(plat_res.products)} products available):\n")
                        for idx, p in enumerate(plat_res.products, 1):
                            eta_str = f"{p.eta_mins}m" if p.eta_mins is not None else "15m"
                            rating_str = f"{p.rating}★" if p.rating is not None else "4.0★ (default)"
                            rev_str = f"({p.rating_count} rev)" if p.rating_count else ""
                            disc_str = f", -{p.discount_pct:.0f}%" if p.discount_pct > 0 else ""
                            brand_str = f" [{p.brand}]" if p.brand else ""
                            f.write(
                                f"    {idx:2d}. [ID: {p.id}] {p.name}{brand_str} | "
                                f"{p.quantity} | Rs.{p.offer_price:.2f} (MRP Rs.{p.mrp:.2f}{disc_str}) | "
                                f"{rating_str} {rev_str} | {eta_str}\n"
                            )
                        f.write("\n")
                f.write("\n")

                # STAGE 3: WORKER 1 EVALUATION
                f.write("[STAGE 3: WORKER 1 (GROQ KEY 1: BlinkIt & Zepto) - AI PICKS]\n")
                for p in worker_1_out.best_picks:
                    brand_match_tag = "[Brand Match]" if p.is_exact_brand_match else "[Alternative]"
                    f.write(f"• Pick: {p.item_name} -> [{p.picked_product_id}] {p.platform} | {p.product_name} | Rs.{p.offer_price:.2f} {brand_match_tag}\n")
                    if p.selection_reason:
                        f.write(f"        Reason: {p.selection_reason}\n")
                for est in worker_1_out.single_store_estimates:
                    status = "All Items" if est.has_all_items else f"Missing: {', '.join(est.missing_items)}"
                    f.write(f"• Store: {est.platform:10s} -> Items: Rs.{est.items_subtotal:.2f} + Fee: Rs.{est.delivery_fee:.2f} = Grand Total: Rs.{est.grand_total:.2f} [{status}]\n")
                f.write("\n")

                # STAGE 4: WORKER 2 EVALUATION
                f.write("[STAGE 4: WORKER 2 (GROQ KEY 2: Swiggy & BigBasket) - AI PICKS]\n")
                for p in worker_2_out.best_picks:
                    brand_match_tag = "[Brand Match]" if p.is_exact_brand_match else "[Alternative]"
                    f.write(f"• Pick: {p.item_name} -> [{p.picked_product_id}] {p.platform} | {p.product_name} | Rs.{p.offer_price:.2f} {brand_match_tag}\n")
                    if p.selection_reason:
                        f.write(f"        Reason: {p.selection_reason}\n")
                for est in worker_2_out.single_store_estimates:
                    status = "All Items" if est.has_all_items else f"Missing: {', '.join(est.missing_items)}"
                    f.write(f"• Store: {est.platform:10s} -> Items: Rs.{est.items_subtotal:.2f} + Fee: Rs.{est.delivery_fee:.2f} = Grand Total: Rs.{est.grand_total:.2f} [{status}]\n")
                f.write("\n")

                # STAGE 5: FINAL CROSS-PLATFORM SYNTHESIS & WINNING RECOMMENDATION
                f.write("[STAGE 5: FINAL SYNTHESIS & WINNING RECOMMENDATION]\n")
                f.write(f"• Strategy          : {winning_combo.combo_type}\n")
                f.write(f"• Winning Platforms : {', '.join(winning_combo.platforms)}\n")
                f.write(f"• Items Subtotal    : Rs.{winning_combo.items_subtotal:.2f}\n")
                f.write(f"• Delivery Fees     : Rs.{winning_combo.total_delivery_fees:.2f}\n")
                f.write(f"• Grand Total       : Rs.{winning_combo.total_price:.2f}\n")
                f.write(f"• Savings vs Highest: Rs.{winning_combo.savings_vs_highest:.2f}\n")
                if winning_combo.fee_explanation:
                    f.write(f"• Fee Arithmetic    : {winning_combo.fee_explanation}\n\n")

                f.write("• Selected Items in Winning Order:\n")
                for order in winning_combo.orders:
                    f.write(f"  [{order.platform}] Subtotal: Rs.{order.items_subtotal:.2f} + Delivery: Rs.{order.delivery_fee:.2f} = Rs.{order.total_order_cost:.2f}\n")
                    for pick in order.items:
                        f.write(f"    - {pick.item_name}: {pick.product.name} | {pick.product.quantity} | Rs.{pick.item_total_price:.2f}\n")
                f.write("\n")

                # STAGE 6: NATURAL LANGUAGE RESPONSE
                f.write("[STAGE 6: NATURAL LANGUAGE RESPONSE]\n")
                f.write(natural_language_response + "\n")
                f.write("\n" + "=" * 90 + "\n\n")
        except Exception as log_err:
            logger.warning(f"Failed to write trace log: {log_err}")

    async def recommend(
        self,
        raw_query: str,
        search_result: MultiItemSearchResult,
    ) -> SahiBhavResponse:
        """
        Executes parallel Dual-Worker Recommender stage:
          1. Formats candidate products into two platform pools (Blinkit+Zepto vs Swiggy+BigBasket).
          2. Runs Worker 1 (Key 1) and Worker 2 (Key 2) concurrently in parallel with asyncio.gather().
          3. Synthesizes winners, calculates single-store vs split delivery fees.
          4. Returns complete SahiBhavResponse.
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

        # 1. Format candidate pools for both workers
        platforms_w1 = ["BlinkIt", "Zepto"]
        platforms_w2 = ["Swiggy", "BigBasket"]

        cand_text_1, p_map_1 = self.format_candidate_pool_for_platforms(search_result, platforms_w1, max_per_platform=8)
        cand_text_2, p_map_2 = self.format_candidate_pool_for_platforms(search_result, platforms_w2, max_per_platform=8)

        # Combined product map for re-hydrating winning picks
        all_product_map: Dict[str, CleanedProduct] = {**p_map_1, **p_map_2}

        # 2. Run Worker 1 & Worker 2 in parallel concurrently!
        task_1 = self._run_worker(
            worker_id="Worker-1 (Key-1)",
            chain=self.worker_1_chain,
            raw_query=raw_query,
            detected_language=search_result.detected_language,
            assigned_platforms=platforms_w1,
            candidate_text=cand_text_1,
            product_map=p_map_1,
            search_result=search_result,
        )

        task_2 = self._run_worker(
            worker_id="Worker-2 (Key-2)",
            chain=self.worker_2_chain,
            raw_query=raw_query,
            detected_language=search_result.detected_language,
            assigned_platforms=platforms_w2,
            candidate_text=cand_text_2,
            product_map=p_map_2,
            search_result=search_result,
        )

        worker_1_out, worker_2_out = await asyncio.gather(task_1, task_2)

        # 3. Build complete single-store carts for all platforms with brand substitutions
        all_worker_picks = worker_1_out.best_picks + worker_2_out.best_picks
        single_combos = self._build_all_single_store_combos(search_result, all_worker_picks)

        # 4. Filter for platforms that have all requested items
        complete_stores = [
            c for c in single_combos
            if len(c.orders[0].items) == len(search_result.items) and c.items_subtotal > 0
        ]
        candidate_stores = complete_stores if complete_stores else [c for c in single_combos if c.items_subtotal > 0]

        if not candidate_stores:
            # Fallback if no store has any items
            fallback_combo = CartCombination(
                combo_type="single_platform",
                platforms=["BlinkIt"],
                orders=[],
                items_subtotal=0.0,
                total_delivery_fees=0.0,
                total_price=0.0,
                savings_vs_highest=0.0,
                fee_explanation="No items could be fulfilled.",
            )
            candidate_stores = [fallback_combo]

        # 5. Determine winning single-platform (lowest grand total)
        candidate_stores.sort(key=lambda c: c.total_price)
        winning_combo = candidate_stores[0]
        strategy = "single_platform"

        # Calculate savings vs highest complete store
        highest_price = max(c.total_price for c in candidate_stores)
        winning_combo.savings_vs_highest = max(0.0, round(highest_price - winning_combo.total_price, 2))
        for c in single_combos:
            c.savings_vs_highest = max(0.0, round(highest_price - c.total_price, 2))

        # Check for brand substitutions in winning cart
        substitutions: List[str] = []
        if winning_combo.orders and winning_combo.orders[0].items:
            for it_pick in winning_combo.orders[0].items:
                orig_req = next((x.item for x in search_result.items if x.item.product_name == it_pick.item_name), None)
                if orig_req and orig_req.brand_preference:
                    pref = orig_req.brand_preference.lower()
                    p_name = it_pick.product.name.lower()
                    p_brand = (it_pick.product.brand or "").lower()
                    if pref not in p_brand and pref not in p_name:
                        substitutions.append(f"{it_pick.item_name}: {it_pick.product.name} (as alternative to {orig_req.brand_preference})")

        sub_note = f" Brand substitute note: {'; '.join(substitutions)}." if substitutions else ""
        fee_str = "FREE" if winning_combo.total_delivery_fees == 0 else f"₹{winning_combo.total_delivery_fees:.0f}"
        plat_winner = winning_combo.platforms[0]
        fee_expl = (
            f"Ordering everything from {plat_winner} fulfills your entire cart on a single platform with "
            f"{'FREE delivery' if winning_combo.total_delivery_fees == 0 else f'₹{winning_combo.total_delivery_fees:.0f} delivery fee'}."
        )
        winning_combo.fee_explanation = fee_expl

        # Localized Natural Language Response
        lang = (search_result.detected_language or "English").lower()
        if "odia" in lang:
            nl_response = (
                f"ଆପଣଙ୍କ ସପିଂ ଲିଷ୍ଟ ପାଇଁ {plat_winner} ଗୋଟିଏ ପ୍ଲାଟଫର୍ମରେ ସବୁଠାରୁ ଶସ୍ତା ଏବଂ ସର୍ବୋତ୍ତମ ବିକଳ୍ପ ଅଟେ! "
                f"ମୋଟ ସାମଗ୍ରୀ ମୂଲ୍ୟ: ₹{winning_combo.items_subtotal:.2f}, ଡେଲିଭରି ଫି: {fee_str}, "
                f"ସମୁଦାୟ: ₹{winning_combo.total_price:.2f}। "
                f"ଗୋଟିଏ ଷ୍ଟୋରରୁ ଅର୍ଡର କରିବା ଦ୍ୱାରା ଅତିରିକ୍ତ ଡେଲିଭରି ଫି ବଞ୍ଚିଯାଏ।{sub_note} "
                f"ଅନ୍ୟ ଷ୍ଟୋର ତୁଳନାରେ ଆପଣ ₹{winning_combo.savings_vs_highest:.2f} ପର୍ଯ୍ୟନ୍ତ ବଞ୍ଚାଇ ପାରିବେ।"
            )
        elif "hindi" in lang:
            nl_response = (
                f"Aapke order ke liye {plat_winner} single platform par sabse kifayati aur best deal hai! "
                f"Items Total: Rs.{winning_combo.items_subtotal:.2f}, Delivery Fee: {fee_str}, "
                f"Grand Total: Rs.{winning_combo.total_price:.2f}। "
                f"Ek hi store se order karne se extra delivery charges nahi lagte.{sub_note} "
                f"Doosre platforms ke mukable aap lagbhag Rs.{winning_combo.savings_vs_highest:.2f} bacha rahe hain."
            )
        else:
            nl_response = (
                f"For your shopping list, {plat_winner} offers the best single-store deal! "
                f"Items Subtotal: Rs.{winning_combo.items_subtotal:.2f}, Delivery Fee: {fee_str}, "
                f"Grand Total: Rs.{winning_combo.total_price:.2f}. "
                f"Ordering everything from one platform avoids split delivery fees.{sub_note} "
                f"You save approx Rs.{winning_combo.savings_vs_highest:.2f} compared to other platforms."
            )

        # 6. Log execution trace
        self.log_trace(
            raw_query=raw_query,
            detected_language=search_result.detected_language,
            search_result=search_result,
            worker_1_out=worker_1_out,
            worker_2_out=worker_2_out,
            winning_combo=winning_combo,
            natural_language_response=nl_response,
        )

        opt_result = OptimizationResult(
            is_valid_grocery_query=True,
            detected_language=search_result.detected_language,
            best_single_store=winning_combo,
            best_split_combo=None,
            winning_recommendation=winning_combo,
            all_single_stores=single_combos,
            all_split_combos=[],
            notes=winning_combo.fee_explanation,
        )

        return SahiBhavResponse(
            raw_query=raw_query,
            detected_language=search_result.detected_language,
            is_valid_grocery_query=True,
            natural_language_response=nl_response,
            optimization=opt_result,
            notes=winning_combo.fee_explanation,
        )
