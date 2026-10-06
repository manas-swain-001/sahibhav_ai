import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

# Ensure src is on sys.path for clean module imports
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from sahibhav_ai.config import DEFAULT_LAT, DEFAULT_LON, SUPPORTED_PLATFORMS
from sahibhav_ai.models import UserIntent, SahiBhavResponse, MultiItemSearchResult
from sahibhav_ai.intent_extractor import IntentExtractor
from sahibhav_ai.stages import (
    MultiItemSearchStage,
    SmartRecommenderStage,
)

# Initialize FastAPI Application
app = FastAPI(
    title="SahiBhav AI API",
    description=(
        "Backend REST API for SahiBhav AI — India's Smartest Quick-Commerce Price "
        "Optimizer & Multi-Platform Shopping Companion across BlinkIt, Zepto, Swiggy, and BigBasket."
    ),
    version="1.0.0",
)

# Configure CORS Middleware (enables React frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev and production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pipeline Singleton Instances
intent_extractor = IntentExtractor()
search_stage = MultiItemSearchStage()
recommender_stage = SmartRecommenderStage()


# =====================================================================
# REQUEST & RESPONSE SCHEMAS
# =====================================================================

class OptimizeRequest(BaseModel):
    query: str = Field(
        ...,
        description="Grocery requirement in any Indian or global language",
        examples=["1 packet milk aur 1 pack butter chahiye"]
    )
    lat: float = Field(default=DEFAULT_LAT)
    lon: Optional[float] = Field(default=None)
    lng: Optional[float] = Field(default=None)
    delivery_mode: Optional[str] = Field(default="instant")
    platforms: Optional[List[str]] = Field(default=None)

    def get_lon(self) -> float:
        if self.lon is not None:
            return self.lon
        if self.lng is not None:
            return self.lng
        return DEFAULT_LON


class IntentRequest(BaseModel):
    query: str = Field(..., description="User query to extract shopping intent from")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    supported_platforms: List[str]
    default_coordinates: dict


# =====================================================================
# API ROUTES
# =====================================================================

@app.get("/", include_in_schema=False)
def root():
    """Redirect root to interactive Swagger UI documentation."""
    return RedirectResponse(url="/docs")


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """
    Health check endpoint for deployment uptime verification.
    """
    return HealthResponse(
        status="ok",
        service="sahibhav-ai",
        version="1.0.0",
        supported_platforms=SUPPORTED_PLATFORMS,
        default_coordinates={"lat": DEFAULT_LAT, "lon": DEFAULT_LON},
    )


@app.get("/api/platforms", tags=["Metadata"])
def get_platforms():
    """
    Returns supported quick-commerce platforms with brand metadata for the UI.
    """
    return {
        "platforms": [
            {
                "id": "BlinkIt",
                "name": "Blinkit",
                "color": "#F8CB46",
                "avg_eta_mins": 10,
                "free_delivery_above": 200.0,
            },
            {
                "id": "Zepto",
                "name": "Zepto",
                "color": "#8B30EC",
                "avg_eta_mins": 10,
                "free_delivery_above": 200.0,
            },
            {
                "id": "Swiggy",
                "name": "Swiggy Instamart",
                "color": "#FC8019",
                "avg_eta_mins": 12,
                "free_delivery_above": 200.0,
            },
            {
                "id": "BigBasket",
                "name": "BigBasket (bbnow)",
                "color": "#84C225",
                "avg_eta_mins": 15,
                "free_delivery_above": 200.0,
            },
        ]
    }


@app.post("/api/intent", response_model=UserIntent, tags=["Pipeline"])
def extract_intent_endpoint(req: IntentRequest):
    """
    Stage 1 only: Extracts structured grocery requirements, quantities, and detected language.
    Useful for UI previews and real-time query chips.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return intent_extractor.extract_intent(req.query)


@app.post("/api/search", response_model=MultiItemSearchResult, tags=["Pipeline"])
async def search_endpoint(req: OptimizeRequest):
    """
    Search & Filter Endpoint:
      1. Takes input query from user (any language).
      2. Extracts shopping intent (items, quantities).
      3. Concurrently finds products across platforms (BlinkIt, Zepto, Swiggy, BigBasket).
      4. Filters products (drops ads, drops out-of-stock, deduplicates by ID).
      5. Returns filtered candidate products grouped by item and platform.
    """
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. Extract Intent
    intent = intent_extractor.extract_intent(query)

    # 2. Find and filter products across all platforms
    search_result = await search_stage.execute(
        intent=intent,
        lat=req.lat,
        lon=req.get_lon(),
        platforms=req.platforms,
    )
    return search_result


@app.post("/api/optimize", response_model=SahiBhavResponse, tags=["Pipeline"])
async def optimize_endpoint(req: OptimizeRequest):
    """
    The Primary Workhorse Endpoint (Full Pipeline with Smart Recommender):
      1. Stage 1: Extracts intent and detects language (Hindi, Odia, English, etc.).
      2. Stage 2: Concurrently searches platforms via live QuickCommerce API.
      3. Stage 3: Smart Recommender LLM evaluates 90/7/3 weights, purity, brand trade-offs, and delivery fees.
    """
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. Stage 1: Intent Extraction
    intent = intent_extractor.extract_intent(query)

    # 2. Stage 2: Multi-Platform Search (Runs if query is valid grocery request)
    search_result = await search_stage.execute(
        intent=intent,
        lat=req.lat,
        lon=req.get_lon(),
        platforms=req.platforms,
    )

    # 3. Stage 3: Smart Recommender LLM (90/7/3 weights, Purity, Brand Advice, Split vs Single Math, Trace Logging)
    final_response = recommender_stage.recommend(
        raw_query=query,
        search_result=search_result,
    )

    return final_response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
