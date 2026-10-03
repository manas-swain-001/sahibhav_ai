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
        price_val = product.price_per_standard_unit if product.price_per_standard_unit > 0 else product.offer_price
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
            valid_prices = [
                p.price_per_standard_unit if p.price_per_standard_unit > 0 else p.offer_price
                for p in all_products_for_item
                if (p.price_per_standard_unit > 0 or p.offer_price > 0)
            ]
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
                    best_prod = max(plat_res.products, key=lambda x: (x.score, -x.offer_price))
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
                total_score += prod.score
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
        # Step 3: Build 2-Platform Split Combinations
        # -------------------------------------------------------------
        split_combos: List[CartCombination] = []

        if len(search_result.items) >= 2 and len(all_platforms) >= 2:
            for p1, p2 in itertools.combinations(sorted(all_platforms), 2):
                # Check if the pair (p1, p2) can cover all items
                pair_can_cover = all((p1 in plat_map or p2 in plat_map) for plat_map in best_picks_by_item)
                if not pair_can_cover:
                    continue

                p1_picks: List[CartItemPick] = []
                p2_picks: List[CartItemPick] = []
                p1_eta: Optional[int] = None
                p2_eta: Optional[int] = None
                total_score = 0.0
                ratings_sum = 0.0

                for idx, item_res in enumerate(search_result.items):
                    prod1 = best_picks_by_item[idx].get(p1)
                    prod2 = best_picks_by_item[idx].get(p2)
                    qty = max(1.0, item_res.item.quantity)

                    # Choose the better platform for this item based on score
                    if prod1 and prod2:
                        chosen_plat, chosen_prod = (p1, prod1) if prod1.score >= prod2.score else (p2, prod2)
                    elif prod1:
                        chosen_plat, chosen_prod = p1, prod1
                    elif prod2:
                        chosen_plat, chosen_prod = p2, prod2
                    else:
                        continue

                    item_cost = round(chosen_prod.offer_price * qty, 2)
                    total_score += chosen_prod.score
                    ratings_sum += (chosen_prod.rating if chosen_prod.rating is not None else self.default_rating)

                    pick = CartItemPick(
                        item_name=item_res.item.product_name,
                        search_query=item_res.item.search_query,
                        quantity_requested=item_res.item.quantity,
                        unit_requested=item_res.item.unit,
                        platform=chosen_plat,
                        product=chosen_prod,
                        item_total_price=item_cost,
                    )

                    if chosen_plat == p1:
                        p1_picks.append(pick)
                        if chosen_prod.eta_mins is not None:
                            p1_eta = max(p1_eta or 0, chosen_prod.eta_mins)
                    else:
                        p2_picks.append(pick)
                        if chosen_prod.eta_mins is not None:
                            p2_eta = max(p2_eta or 0, chosen_prod.eta_mins)

                # A true split requires items on BOTH platforms
                if not p1_picks or not p2_picks:
                    continue

                p1_items_subtotal = round(sum(x.item_total_price for x in p1_picks), 2)
                p1_fee = self.calculate_delivery_fee(p1_items_subtotal)
                p1_total = round(p1_items_subtotal + p1_fee, 2)

                p2_items_subtotal = round(sum(x.item_total_price for x in p2_picks), 2)
                p2_fee = self.calculate_delivery_fee(p2_items_subtotal)
                p2_total = round(p2_items_subtotal + p2_fee, 2)

                p1_order = PlatformOrder(
                    platform=p1,
                    items=p1_picks,
                    items_subtotal=p1_items_subtotal,
                    delivery_fee=p1_fee,
                    total_order_cost=p1_total,
                    subtotal=p1_total,
                    eta_mins=p1_eta,
                )
                p2_order = PlatformOrder(
                    platform=p2,
                    items=p2_picks,
                    items_subtotal=p2_items_subtotal,
                    delivery_fee=p2_fee,
                    total_order_cost=p2_total,
                    subtotal=p2_total,
                    eta_mins=p2_eta,
                )

                orders = [p1_order, p2_order]
                combined_items = round(p1_items_subtotal + p2_items_subtotal, 2)
                combined_fees = round(p1_fee + p2_fee, 2)
                grand_total = round(combined_items + combined_fees, 2)
                overall_max_eta = max(p1_eta or 0, p2_eta or 0) or None
                num_items = len(search_result.items)

                split_combos.append(CartCombination(
                    combo_type="split_2_platform",
                    platforms=[p1, p2],
                    orders=orders,
                    items_subtotal=combined_items,
                    total_delivery_fees=combined_fees,
                    total_price=grand_total,
                    max_eta_mins=overall_max_eta,
                    average_rating=round(ratings_sum / num_items, 2) if num_items else 4.0,
                    composite_score=round(total_score / num_items, 2) if num_items else 0.0,
                ))

        # -------------------------------------------------------------
        # Step 4: Calculate Net Savings & Determine Winners
        # -------------------------------------------------------------
        # Sort single stores by grand total price (ascending), then composite_score (descending)
        single_stores.sort(key=lambda x: (x.total_price, -x.composite_score))
        # Sort split combos by grand total price (ascending), then composite_score (descending)
        split_combos.sort(key=lambda x: (x.total_price, -x.composite_score))

        best_single_store = single_stores[0] if single_stores else None
        best_split_combo = split_combos[0] if split_combos else None

        # Highest grand total price benchmark across all single stores
        highest_price = max((c.total_price for c in single_stores), default=0.0)

        # Compute savings for all combinations
        for combo in itertools.chain(single_stores, split_combos):
            if highest_price > 0:
                combo.savings_vs_highest = max(0.0, round(highest_price - combo.total_price, 2))

            if best_single_store:
                if combo.total_price < best_single_store.total_price:
                    combo.savings_vs_best_single = round(best_single_store.total_price - combo.total_price, 2)
                    combo.is_split_beneficial = True
                    combo.fee_explanation = (
                        f"Splitting saves ₹{combo.savings_vs_best_single:.2f} net (items + delivery charges included)!"
                    )
                else:
                    extra_cost = round(combo.total_price - best_single_store.total_price, 2)
                    combo.savings_vs_best_single = 0.0
                    combo.is_split_beneficial = False
                    if combo.combo_type == "split_2_platform":
                        combo.fee_explanation = (
                            f"Splitting costs ₹{extra_cost:.2f} more due to ₹{combo.total_delivery_fees:.2f} "
                            f"in separate delivery fees. Best single store on {best_single_store.platforms[0]} is cheaper!"
                        )

        # -------------------------------------------------------------
        # Step 5: Pick Winning Recommendation (Single-Store First Policy)
        # -------------------------------------------------------------
        winning_recommendation: Optional[CartCombination] = None

        if best_split_combo and best_single_store:
            # Only recommend split if it is STRICTLY cheaper on Grand Total
            if best_split_combo.is_split_beneficial and best_split_combo.total_price < best_single_store.total_price:
                winning_recommendation = best_split_combo
            else:
                # Single store is preferred for convenience whenever prices are equal or split is costlier
                winning_recommendation = best_single_store
        elif best_single_store:
            winning_recommendation = best_single_store
        elif best_split_combo:
            winning_recommendation = best_split_combo

        return OptimizationResult(
            is_valid_grocery_query=True,
            detected_language=search_result.detected_language,
            best_single_store=best_single_store,
            best_split_combo=best_split_combo,
            winning_recommendation=winning_recommendation,
            all_single_stores=single_stores,
            all_split_combos=split_combos,
            notes=search_result.notes,
        )
