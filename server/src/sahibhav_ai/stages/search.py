import asyncio
from typing import List, Optional
from ..models import UserIntent, ItemRequirement, ItemSearchResult, MultiItemSearchResult
from ..client.qc_client import QuickCommerceClient
from ..config import DEFAULT_LAT, DEFAULT_LON, SUPPORTED_PLATFORMS


class MultiItemSearchStage:
    """
    Responsibilities:
      1. Receives structured UserIntent from Intent Extractor (e.g., items: ["milk", "atta"]).
      2. If intent is invalid or off-topic, returns safely with 0 searches.
      3. For each requested item, concurrently executes multi-platform searches
         (BlinkIt, Zepto, Swiggy Instamart, BigBasket) using QuickCommerceClient.
      4. Aggregates cleaned, deduplicated, and normalized product lists per item.
      5. Prepares candidate product pools for Combo Optimizer.
    """

    def __init__(self, client: Optional[QuickCommerceClient] = None):
        self.client = client or QuickCommerceClient()

    async def search_single_item(
        self,
        item: ItemRequirement,
        lat: float,
        lon: float,
        platforms: Optional[List[str]] = None,
    ) -> ItemSearchResult:
        """
        Runs search across all platforms for a single item requirement.
        """
        platform_results = await self.client.search_all(
            query=item.search_query,
            lat=lat,
            lon=lon,
            platforms=platforms,
        )

        total_cleaned = sum(res.total_results for res in platform_results.values())

        return ItemSearchResult(
            item=item,
            platforms=platform_results,
            total_cleaned_products=total_cleaned,
        )

    async def execute(
        self,
        intent: UserIntent,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
        platforms: Optional[List[str]] = None,
    ) -> MultiItemSearchResult:
        """
        Executes multi-item search pipeline for all items in the user intent concurrently.
        """
        # Guardrail check: if intent was flagged as invalid or off-topic
        if not intent.is_valid_grocery_query or not intent.items:
            return MultiItemSearchResult(
                is_valid_grocery_query=intent.is_valid_grocery_query,
                detected_language=intent.detected_language,
                items=[],
                total_items=0,
                total_products_found=0,
                notes=intent.notes or "No grocery items to search.",
            )

        target_platforms = platforms or SUPPORTED_PLATFORMS

        # Run parallel searches across all requested items simultaneously
        tasks = [
            self.search_single_item(
                item=item,
                lat=lat,
                lon=lon,
                platforms=target_platforms,
            )
            for item in intent.items
        ]

        item_results: List[ItemSearchResult] = await asyncio.gather(*tasks)

        total_products_found = sum(res.total_cleaned_products for res in item_results)

        return MultiItemSearchResult(
            is_valid_grocery_query=True,
            detected_language=intent.detected_language,
            items=item_results,
            total_items=len(item_results),
            total_products_found=total_products_found,
            notes=intent.notes,
        )
