import asyncio
from typing import List, Dict, Optional, Any
import httpx

from ..config import (
    QUICKCOMMERCE_API_KEY,
    QC_BASE_URL,
    DEFAULT_LAT,
    DEFAULT_LON,
    SUPPORTED_PLATFORMS,
)
from ..models import RawProduct, PlatformSearchResult
from ..tools.relevance import filter_relevance
from ..tools.dedupe import dedupe_products
from ..tools.normalizer import normalize_product


class QuickCommerceClient:
    """
    Search Client for BlinkIt, Zepto, Swiggy Instamart, and BigBasket.
    
    Direct live search mode via QuickCommerce HTTP API:
      - Uses httpx.AsyncClient with X-API-Key
      - Parallel execution across all 4 platforms using asyncio.gather
      - Automatic parsing, filtering (ads, OOS, irrelevant), deduplicating, and normalization
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or QUICKCOMMERCE_API_KEY
        self.base_url = base_url or QC_BASE_URL

    async def search_platform(
        self,
        platform: str,
        query: str,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
    ) -> PlatformSearchResult:
        """
        Searches a single quick-commerce platform using live API and applies full cleaning & normalization.
        """
        raw_products_data: List[Dict[str, Any]] = []
        error_msg: Optional[str] = None

        if not self.api_key:
            return PlatformSearchResult(
                platform=platform,
                query=query,
                error="QuickCommerce API key is not configured in .env"
            )

        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json"
        }
        params = {
            "q": query,
            "lat": str(lat),
            "lon": str(lon),
            "platform": platform
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.base_url, headers=headers, params=params)
                if resp.status_code == 200:
                    payload = resp.json()
                    raw_products_data = payload.get("data", {}).get("products", [])
                else:
                    error_msg = f"API Error {resp.status_code}: {resp.text[:150]}"
        except Exception as e:
            error_msg = f"Network exception: {str(e)}"

        if error_msg and not raw_products_data:
            return PlatformSearchResult(
                platform=platform,
                query=query,
                error=error_msg
            )

        # 1. Parse into RawProduct models (with automatic type coercion)
        raw_products = [RawProduct(**p) for p in raw_products_data]
        raw_count = len(raw_products)

        # 2. Filter Ads, OOS, and Irrelevant matches
        relevant_products, ads_dropped, oos_dropped, irrelevant_dropped = await filter_relevance(
            products=raw_products,
            search_query=query
        )

        # 3. Deduplicate (e.g. Swiggy duplicate IDs)
        deduped_products = dedupe_products(relevant_products)

        # 4. Normalize to standardized CleanedProduct
        cleaned_products = [
            normalize_product(p, fallback_platform_name=platform)
            for p in deduped_products
        ]

        return PlatformSearchResult(
            platform=platform,
            query=query,
            total_results=len(cleaned_products),
            products=cleaned_products,
            raw_count=raw_count,
            filtered_ads_count=ads_dropped,
            filtered_oos_count=oos_dropped,
            filtered_irrelevant_count=irrelevant_dropped,
            error=error_msg
        )

    async def search_all(
        self,
        query: str,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, PlatformSearchResult]:
        """
        Executes parallel live searches across all 4 platforms simultaneously using asyncio.gather.
        """
        target_platforms = platforms or SUPPORTED_PLATFORMS

        tasks = [
            self.search_platform(
                platform=p,
                query=query,
                lat=lat,
                lon=lon
            )
            for p in target_platforms
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: Dict[str, PlatformSearchResult] = {}
        for p, res in zip(target_platforms, results):
            if isinstance(res, BaseException):
                output[p] = PlatformSearchResult(
                    platform=p,
                    query=query,
                    error=str(res)
                )
            else:
                output[p] = res

        return output
