import os
import asyncio
from typing import List, Dict, Optional, Any
import httpx
from dotenv import load_dotenv

from ..config import (
    ENV_PATH,
    QUICKCOMMERCE_API_KEY,
    QUICKCOMMERCE_API_KEYS,
    QC_BASE_URL,
    DEFAULT_LAT,
    DEFAULT_LON,
    SUPPORTED_PLATFORMS,
)
from ..models import RawProduct, CleanedProduct, PlatformSearchResult
from ..tools.pre_filter import clean_and_dedupe
from ..tools.eta_parser import parse_eta


class QuickCommerceClient:
    """
    Search Client for BlinkIt, Zepto, Swiggy Instamart, and BigBasket.
    
    Direct live search mode via QuickCommerce HTTP API:
      - Uses httpx.AsyncClient with X-API-Key
      - Dynamic key reloading directly from .env (no server restart needed when user updates token)
      - Key rotation across available API keys (with failover on 402/429)
      - Parallel execution across all 4 platforms using asyncio.gather
      - Lightweight pre-filtering (ads, OOS, deduplication)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._static_api_key = api_key
        self.base_url = base_url or QC_BASE_URL
        self._key_index = 0

    def get_active_keys(self) -> List[str]:
        """
        Dynamically loads the latest keys from .env so when the user adds a new token,
        it takes effect immediately without needing to restart the server.
        """
        if self._static_api_key:
            return [self._static_api_key]
        try:
            load_dotenv(dotenv_path=ENV_PATH, override=True)
        except Exception:
            pass

        key = os.getenv("QUICK_COMMERCE_API_KEY") or os.getenv("QUICKCOMMERCE_API_KEY", "")
        keys_raw = os.getenv("QUICK_COMMERCE_API_KEYS", "")
        keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
        if key and key not in keys:
            keys.insert(0, key)
        return keys or list(QUICKCOMMERCE_API_KEYS)

    async def search_platform(
        self,
        platform: str,
        query: str,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
    ) -> PlatformSearchResult:
        """
        Searches a single quick-commerce platform using live API and applies lightweight pre-filtering.
        """
        raw_products_data: List[Dict[str, Any]] = []
        error_msg: Optional[str] = None

        keys_to_try = self.get_active_keys()
        if not keys_to_try:
            return PlatformSearchResult(
                platform=platform,
                query=query,
                error="QuickCommerce API key is not configured in .env"
            )

        params = {
            "q": query,
            "lat": str(lat),
            "lon": str(lon),
            "platform": platform
        }

        # Try available keys with automatic failover if credit exhausted (402)
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(len(keys_to_try)):
                active_key = keys_to_try[(self._key_index + attempt) % len(keys_to_try)]
                headers = {
                    "X-API-Key": active_key,
                    "Accept": "application/json"
                }
                try:
                    resp = await client.get(self.base_url, headers=headers, params=params)
                    if resp.status_code == 200:
                        payload = resp.json()
                        raw_products_data = payload.get("data", {}).get("products", [])
                        error_msg = None
                        # Update index for light round-robin distribution
                        self._key_index = (self._key_index + attempt) % len(keys_to_try)
                        break
                    elif resp.status_code in (402, 429):
                        # Credit exhausted on this key, try next key
                        error_msg = f"API Error {resp.status_code}: {resp.text[:100]}"
                        continue
                    else:
                        error_msg = f"API Error {resp.status_code}: {resp.text[:150]}"
                        break
                except Exception as e:
                    error_msg = f"Network exception: {str(e)}"
                    break

        if error_msg and not raw_products_data:
            return PlatformSearchResult(
                platform=platform,
                query=query,
                error=error_msg
            )

        # 1. Parse into RawProduct models (with automatic type coercion)
        raw_products = [RawProduct(**p) for p in raw_products_data]
        raw_count = len(raw_products)

        # 2. Pre-filter: Drop ads, OOS, and deduplicate
        filtered_products, ads_dropped, oos_dropped = clean_and_dedupe(raw_products)

        # 3. Convert to simplified CleanedProduct (no normalization/parsing needed — LLM handles it)
        cleaned_products = []
        for p in filtered_products:
            eta_mins = parse_eta(p.platform.sla if p.platform else None)
            image_url = p.images[0] if (p.images and len(p.images) > 0) else None
            platform_name = p.platform.name if p.platform else platform

            cleaned_products.append(CleanedProduct(
                id=str(p.id),
                platform_name=platform_name,
                name=p.name.strip(),
                brand=p.brand.strip() if p.brand else None,
                mrp=round(p.mrp, 2),
                offer_price=round(p.offer_price, 2),
                quantity=p.quantity,
                rating=p.rating,
                rating_count=p.rating_count,
                eta_mins=eta_mins,
                deeplink=p.deeplink,
                image_url=image_url,
                is_available=p.available,
            ))

        return PlatformSearchResult(
            platform=platform,
            query=query,
            total_results=len(cleaned_products),
            products=cleaned_products,
            raw_count=raw_count,
            filtered_ads_count=ads_dropped,
            filtered_oos_count=oos_dropped,
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
