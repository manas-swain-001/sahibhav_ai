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
