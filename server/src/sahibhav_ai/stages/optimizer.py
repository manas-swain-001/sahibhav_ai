import itertools
from typing import List, Dict, Optional, Tuple
from ..models import (
    MultiItemSearchResult,
    CleanedProduct,
    CartItemPick,
    PlatformOrder,
    CartCombination,
    OptimizationResult,
)

# Scoring Weights
PRICE_WEIGHT = 0.70
ETA_WEIGHT = 0.25
RATING_WEIGHT = 0.05
DEFAULT_RATING = 4.0  # Fair neutral baseline for BigBasket & unrated items

# Quick-Commerce Fee Rules
DELIVERY_FEE = 30.0             # Standard delivery / small-cart fee per platform
FREE_DELIVERY_THRESHOLD = 200.0  # Orders at or above ₹200 get free delivery


class ComboOptimizer:
    """
    Evaluates catalog search results across quick-commerce platforms to find:
      1. Best individual product on each platform using the 70/25/5 scoring formula.
      2. Best single-platform order (for maximum convenience).
      3. Best 2-platform split combination (accounting for delivery fees).
      4. True net savings considering ₹30 delivery charges (< ₹200) vs free delivery (>= ₹200).
    """

    def __init__(
        self,
        price_weight: float = PRICE_WEIGHT,
        eta_weight: float = ETA_WEIGHT,
        rating_weight: float = RATING_WEIGHT,
        default_rating: float = DEFAULT_RATING,
        delivery_fee: float = DELIVERY_FEE,
        free_delivery_threshold: float = FREE_DELIVERY_THRESHOLD,
    ):
        self.price_weight = price_weight
        self.eta_weight = eta_weight
        self.rating_weight = rating_weight
        self.default_rating = default_rating
        self.delivery_fee = delivery_fee
        self.free_delivery_threshold = free_delivery_threshold

    def calculate_delivery_fee(self, subtotal: float) -> float:
        """
        Quick-commerce delivery fee rule:
          - Free delivery (₹0) if platform items subtotal >= ₹200
          - ₹30 delivery fee if subtotal < ₹200
        """
        if subtotal <= 0:
            return 0.0
        if subtotal >= self.free_delivery_threshold:
            return 0.0
        return self.delivery_fee

    def score_product(
        self,
        product: CleanedProduct,
        min_price: float,
        min_eta: int,
    ) -> float:
        """
        Calculates a 0-100 composite score for a product:
          - 70% Price Score (using standardized unit price / offer price)
          - 25% ETA Score (delivery speed)
          - 5% Rating Score (default 4.0★ if rating is null)
        """
        # 1. Price Score (lower price = higher score)
        price_val = (
            product.price_per_standard_unit
            if (product.price_per_standard_unit is not None and product.price_per_standard_unit > 0)
            else product.offer_price
        )
        if price_val > 0 and min_price > 0:
            price_score = min(100.0, (min_price / price_val) * 100.0)
        else:
            price_score = 50.0

        # 2. ETA Score (faster delivery = higher score)
        eta_val = product.eta_mins if (product.eta_mins is not None and product.eta_mins > 0) else 15
        if eta_val > 0 and min_eta > 0:
            eta_score = min(100.0, (min_eta / eta_val) * 100.0)
        else:
            eta_score = 50.0

        # 3. Rating Score (higher rating = higher score, default 4.0 if null)
        eff_rating = product.rating if (product.rating is not None and product.rating > 0) else self.default_rating
        rating_score = min(100.0, (eff_rating / 5.0) * 100.0)

        # Composite weighted sum
        final_score = (
            (self.price_weight * price_score)
            + (self.eta_weight * eta_score)
            + (self.rating_weight * rating_score)
        )
        return round(final_score, 2)

    def optimize(self, search_result: MultiItemSearchResult) -> OptimizationResult:
        """
        Runs complete optimization on multi-item search results.
        """
        if not search_result.is_valid_grocery_query or not search_result.items:
            return OptimizationResult(
                is_valid_grocery_query=search_result.is_valid_grocery_query,
                detected_language=search_result.detected_language,
                notes=search_result.notes or "No items available to optimize.",
            )

        # -------------------------------------------------------------
        # Step 1: Score all products within each item candidate pool
        # -------------------------------------------------------------
        best_picks_by_item: List[Dict[str, CleanedProduct]] = []

        for item_res in search_result.items:
            all_products_for_item: List[CleanedProduct] = []
            for plat_res in item_res.platforms.values():
                all_products_for_item.extend(plat_res.products)

            if not all_products_for_item:
                best_picks_by_item.append({})
                continue

            # Compute min price and min eta across all platforms for this item
            valid_prices: List[float] = []
            for p in all_products_for_item:
                unit_price = p.price_per_standard_unit
                candidate = unit_price if (unit_price is not None and unit_price > 0) else p.offer_price
                if candidate > 0:
                    valid_prices.append(candidate)
            min_price = min(valid_prices) if valid_prices else 1.0

            valid_etas = [
                p.eta_mins for p in all_products_for_item
                if p.eta_mins is not None and p.eta_mins > 0
            ]
            min_eta = min(valid_etas) if valid_etas else 10

            # Score each product and record score on the product
            for p in all_products_for_item:
                p.score = self.score_product(p, min_price=min_price, min_eta=min_eta)

            # Find the best product on each platform for this item
            platform_best: Dict[str, CleanedProduct] = {}
            for plat_name, plat_res in item_res.platforms.items():
                if plat_res.products:
                    # Sort primarily by composite score, then offer_price
                    best_prod = max(
                        plat_res.products,
                        key=lambda x: (x.score if x.score is not None else 0.0, -x.offer_price),
                    )
                    platform_best[plat_name] = best_prod

            best_picks_by_item.append(platform_best)

        # -------------------------------------------------------------
        # Step 2: Build Single-Platform Combinations
        # -------------------------------------------------------------
        all_platforms = set()
        for plat_map in best_picks_by_item:
            all_platforms.update(plat_map.keys())

        single_stores: List[CartCombination] = []

        for plat in sorted(all_platforms):
            # Check if this platform has all requested items
            has_all_items = all(plat in plat_map for plat_map in best_picks_by_item)
            if not has_all_items:
                continue

            order_items: List[CartItemPick] = []
            items_subtotal = 0.0
            order_eta: Optional[int] = None
            total_score = 0.0
            ratings_sum = 0.0

            for idx, item_res in enumerate(search_result.items):
                prod = best_picks_by_item[idx][plat]
                qty = max(1.0, item_res.item.quantity)
                item_cost = round(prod.offer_price * qty, 2)
                items_subtotal += item_cost
                total_score += prod.score if prod.score is not None else 0.0
                ratings_sum += (prod.rating if prod.rating is not None else self.default_rating)

                if prod.eta_mins is not None:
                    order_eta = max(order_eta or 0, prod.eta_mins)

                order_items.append(CartItemPick(
                    item_name=item_res.item.product_name,
                    search_query=item_res.item.search_query,
                    quantity_requested=item_res.item.quantity,
                    unit_requested=item_res.item.unit,
                    platform=plat,
                    product=prod,
                    item_total_price=item_cost,
                ))

            items_subtotal = round(items_subtotal, 2)
            delivery_fee = self.calculate_delivery_fee(items_subtotal)
            grand_total = round(items_subtotal + delivery_fee, 2)

            platform_order = PlatformOrder(
                platform=plat,
                items=order_items,
                items_subtotal=items_subtotal,
                delivery_fee=delivery_fee,
                total_order_cost=grand_total,
                subtotal=grand_total,
                eta_mins=order_eta,
            )

            num_items = len(search_result.items)
            combo = CartCombination(
                combo_type="single_platform",
                platforms=[plat],
                orders=[platform_order],
                items_subtotal=items_subtotal,
                total_delivery_fees=delivery_fee,
                total_price=grand_total,
                max_eta_mins=order_eta,
                average_rating=round(ratings_sum / num_items, 2) if num_items else 4.0,
                composite_score=round(total_score / num_items, 2) if num_items else 0.0,
                is_split_beneficial=False,
            )
            single_stores.append(combo)

        # -------------------------------------------------------------
        # Step 3: Single Platform Policy (No Splitting)
        # -------------------------------------------------------------
        # Filter stores that have items
        valid_stores = [s for s in single_stores if s.items_subtotal > 0]
        valid_stores.sort(key=lambda x: (x.total_price, -x.composite_score))

        best_single_store = valid_stores[0] if valid_stores else None
        highest_price = max((c.total_price for c in valid_stores), default=0.0)

        for combo in valid_stores:
            if highest_price > 0:
                combo.savings_vs_highest = max(0.0, round(highest_price - combo.total_price, 2))
            combo.savings_vs_best_single = 0.0
            combo.is_split_beneficial = False

        return OptimizationResult(
            is_valid_grocery_query=True,
            detected_language=search_result.detected_language,
            best_single_store=best_single_store,
            best_split_combo=None,
            winning_recommendation=best_single_store,
            all_single_stores=valid_stores,
            all_split_combos=[],
            notes=search_result.notes,
        )
