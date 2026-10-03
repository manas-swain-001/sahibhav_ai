from typing import List, Optional
from pydantic import BaseModel, Field

class ItemRequirement(BaseModel):
    raw_item: str = Field(
        ...,
        description="The exact snippet from user's message describing this item (e.g. '2 packet doodh')"
    )
    product_name: str = Field(
        ...,
        description="Normalized English product name (e.g. 'Milk', 'Wheat Flour', 'Eggs', 'Butter')"
    )
    search_query: str = Field(
        ...,
        description="Optimized search keyword for Indian quick commerce apps (e.g. 'milk', 'atta', 'bread', 'amul butter')"
    )
    quantity: float = Field(
        default=1.0,
        description="Quantity amount requested, e.g. 1, 2, 0.5, 5"
    )
    unit: str = Field(
        default="pack",
        description="Unit of measurement: 'pack', 'piece', 'liter', 'ml', 'kg', 'gm', 'dozen', etc."
    )
    brand_preference: Optional[str] = Field(
        default=None,
        description="Preferred brand if mentioned by user (e.g. 'Amul', 'Aashirvaad', 'Mother Dairy', 'Fortune', 'Britannia', or None)"
    )
    category: Optional[str] = Field(
        default=None,
        description="Category like 'Dairy', 'Atta & Flour', 'Bakery', 'Vegetables', 'Beverages', etc."
    )

class UserIntent(BaseModel):
    raw_query: str = Field(
        ...,
        description="Original unmodified user query"
    )
    detected_language: str = Field(
        ...,
        description="Language detected: 'hindi', 'hinglish', or 'english'"
    )
    is_valid_grocery_query: bool = Field(
        default=True,
        description="True if the query is a genuine grocery/quick-commerce shopping request. False if it is unrelated (e.g. coding, general trivia, weather, philosophy, general chat)."
    )
    items: List[ItemRequirement] = Field(
        default_factory=list,
        description="List of extracted grocery/household items requested. MUST BE EMPTY if is_valid_grocery_query is False."
    )
    notes: Optional[str] = Field(
        default=None,
        description="User shopping preferences, urgency notes, or explanation if query was rejected as off-topic."
    )


# =====================================================================
# QUICKCOMMERCE RAW API MODELS (With Robust Type Coercion)
# =====================================================================

class RawPlatformInfo(BaseModel):
    name: str
    sla: Optional[str] = None
    open: bool = True
    icon: Optional[str] = None


class RawProduct(BaseModel):
    id: str
    name: str
    brand: Optional[str] = None
    available: bool = True
    images: List[str] = Field(default_factory=list)
    mrp: float = 0.0
    offer_price: float = 0.0
    quantity: str = ""
    deeplink: Optional[str] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    inventory: Optional[int] = None
    is_ad: bool = False
    rank: Optional[int] = None
    platform: Optional[RawPlatformInfo] = None
    store_id: Optional[str] = None

    from pydantic import field_validator

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v):
        return str(v) if v is not None else ""

    @field_validator("mrp", "offer_price", mode="before")
    @classmethod
    def coerce_price(cls, v):
        if v is None or v == "":
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("rating", mode="before")
    @classmethod
    def round_rating(cls, v):
        if v is None:
            return None
        try:
            return round(float(v), 1)
        except (ValueError, TypeError):
            return None

    @field_validator("rating_count", "inventory", "rank", mode="before")
    @classmethod
    def coerce_int(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("store_id", mode="before")
    @classmethod
    def coerce_store_id(cls, v):
        return str(v) if v is not None else None


# =====================================================================
# STANDARDIZED & CLEANED PRODUCT MODELS FOR OPTIMIZATION
# =====================================================================

class CleanedProduct(BaseModel):
    id: str
    platform_name: str
    name: str
    brand: Optional[str] = None
    mrp: float
    offer_price: float
    discount_pct: float = 0.0
    raw_quantity: str
    parsed_quantity: float
    parsed_unit: str  # 'ml', 'g', 'pack', 'pc'
    standard_unit: str  # '500ml', '1kg', 'pack'
    price_per_standard_unit: float
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    eta_mins: Optional[int] = None
    deeplink: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool = True
    score: float = 0.0  # composite score: 60% price + 25% rating + 15% ETA


class PlatformSearchResult(BaseModel):
    platform: str
    query: str
    total_results: int = 0
    products: List[CleanedProduct] = Field(default_factory=list)
    raw_count: int = 0
    filtered_ads_count: int = 0
    filtered_oos_count: int = 0
    filtered_irrelevant_count: int = 0
    error: Optional[str] = None