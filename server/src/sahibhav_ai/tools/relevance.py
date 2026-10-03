import asyncio
import os
from typing import List, Tuple, Optional, cast
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, SecretStr

from ..config import GROQ_API_KEY, PRIMARY_MODEL, FALLBACK_MODEL
from ..models import RawProduct


class RelevanceDecision(BaseModel):
    """
    Structured response from the LLM classifying product relevance.
    """
    relevant_ids: List[str] = Field(
        default_factory=list,
        description="List of product IDs that genuinely match the user's intent."
    )
    irrelevant_ids: List[str] = Field(
        default_factory=list,
        description="List of product IDs that are off-topic, derivative snacks/foods, appliances/cookware, cross-sells, or unrelated categories."
    )


SYSTEM_RELEVANCE_PROMPT = """You are an expert Indian quick-commerce catalog relevance auditor for SahiBhav AI.
Your job is to identify and filter out off-topic, cross-sell, derivative, utensil/hardware, or search-bleed products ("crows among pigeons") returned by fuzzy platform searches (Blinkit, Zepto, Swiggy Instamart, BigBasket).

============================================================
CORE INTENT AUDITING PRINCIPLES (Apply to ANY search query):
============================================================

1. The "Core Product vs. Derivative / Flavored Snack" Principle:
   - When a user searches for a raw ingredient or core staple/beverage, they want that core product itself.
   - REJECT items where the search term is merely a flavoring, secondary ingredient, or brand name in a processed snack, biscuit, confectionery, or ready-to-eat meal.

2. The "Consumable vs. Cookware / Hardware / Accessory" Principle:
   - Food/grocery searches must NEVER match physical equipment, kitchen tools, appliances, storage containers, or accessories used to prepare or serve that food.

3. The "Category & Homonym Disambiguation" Principle:
   - Disambiguate homonyms and cross-category keyword collisions (e.g. edible cooking oil vs hair oil/cosmetics; food vs books/novels; fruit vs electronics). Default to the primary grocery/FMCG meaning intended by a household shopper.

4. True Variants to Always KEEP:
   - KEEP genuine products across all brands (e.g. Amul, Nandini, Milky Moo, Omfed, Mother Dairy, Akshayakalpa, Pillsbury, Aashirvaad, Tata, Fortune, Dawat, Daawat, Saffola, Surf Excel, etc.).
   - KEEP all valid pack sizes, weights, and packaging formats (pouches, tetra packs, bottles, cans, boxes, loose).
   - KEEP dietary & processing variants if the core product matches (e.g. organic, A2, toned, full cream, lactose-free, unpolished, iodized, sugar-free, refined, cold-pressed).

============================================================
MULTI-CATEGORY BENCHMARK EXAMPLES:
============================================================

• Dairy & Cold Chain:
  - "milk" -> KEEP: Cow Milk, Toned Milk, Full Cream, Tetra Pack, Lactose-Free, A2 Buffalo Milk, Skimmed Milk.
              REJECT: Milk Bread, Milk Bikis (Biscuits), Dairy Milk (Chocolate), Milk Pan (Cookware), Milk Soap, Milk Cake (Sweet), Milkybar candy.
  - "butter" -> KEEP: Salted Table Butter, Unsalted Butter, Cooking Butter, Garlic Butter, White Butter, Margarine/Buttery Spreads.
                REJECT: "Butter" novel/book, Butter Cookies, Butter Popcorn, Butter Chicken Gravy, Spiced Buttermilk / Chaas (Chaas is a drink, not butter!), Body Butter cream.
  - "paneer" -> KEEP: Fresh Paneer cubes/blocks, Malai Paneer, Low-Fat Paneer.
                REJECT: Paneer Butter Masala ready gravy/paste, Paneer Tikka snacks/namkeen.
  - "cheese" -> KEEP: Cheese slices, Cheese blocks, Mozzarella, Processed cheese cubes, Cheese spreads.
                REJECT: Cheese balls (snacks), Cheese crackers, Mac & Cheese ready meal.
  - "curd" / "dahi" -> KEEP: Plain Dahi/Curd, Cow Milk Dahi, Probiotic Dahi, Set Curd.
                       REJECT: Curd Rice ready-to-eat meal, Spiced Chaas/Lassi (unless user asked for lassi/chaas).

• Staples & Grains:
  - "atta" -> KEEP: Chakki Fresh Atta, Whole Wheat Atta, Sharbati Atta, Multigrain Atta, Khapli/Emmer Atta.
              REJECT: Atta Noodles/Maggi, Atta Biscuits/Cookies, Bread.
  - "rice" -> KEEP: Basmati Rice, Sona Masoori, Kolam, Brown Rice, Jasmine Rice, Boiled/Parboiled Rice.
              REJECT: Rice Cooker (Appliance), Rice Bran Cooking Oil, Rice Flour, Puffed Rice/Murmura, Rice Flakes/Poha.
  - "dal" / "toor dal" -> KEEP: Toor Dal, Arhar Dal, Unpolished Dal, Organic Dal.
                          REJECT: Dal Makhani ready-to-eat meal, Dal Tadka spice mix, Moong Dal namkeen/snacks.
  - "sugar" -> KEEP: White Crystal Sugar, Brown Sugar, Bura, Demerara Sugar, Sugar Cubes.
               REJECT: Sugar-Free Sweeteners (unless user asked for sugar-free/stevia), Sugar-Free Biscuits, Sugar Body Scrub.

• Fresh Produce & Fruits:
  - "apple" -> KEEP: Royal Gala, Shimla, Washington, Fuji, Green Apples, Kinnaur Apples.
               REJECT: Apple iPhone chargers/accessories, Apple Cider Vinegar, Apple Juice / Fizzy drinks, Apple Jam.
  - "onion" / "pyaz" -> KEEP: Red Onions, White Onions, Sambhar Onions, Spring Onions.
                        REJECT: Onion Hair Oil, Onion Shampoo, Onion Ring Snacks.
  - "potato" / "aloo" -> KEEP: Fresh Potatoes, Baby Potatoes, Organic Potatoes.
                         REJECT: Potato Chips / Wafers, Aloo Bhujia / Namkeen.
  - "tomato" -> KEEP: Fresh Red Tomatoes, Hybrid Tomatoes, Country/Desi Tomatoes.
                REJECT: Tomato Ketchup, Tomato Soup packets, Tomato Puree / Paste cans.

• Beverages:
  - "tea" / "chai" -> KEEP: CTC Tea leaves, Loose Leaf Tea, Tea Bags, Masala Chai, Green Tea.
                      REJECT: Tea Strainer / Chhanni, Teapot / Kettle, Iced Tea cans/bottles, Tea Rusks.
  - "coffee" -> KEEP: Instant Coffee powder, Roast & Ground Filter Coffee, Coffee Beans.
                REJECT: Coffee Mug / Cups, Coffee French Press / Machine, Coffee Biscuits / Tiramisu, Coffee Face Scrub.

• Cooking Oils & Ghee:
  - "mustard oil" / "sarson tel" -> KEEP: Kachi Ghani Mustard Oil, Pure Cold-Pressed Mustard Oil.
                                    REJECT: Mustard Sauce / Kasundi, Hair Oils.
  - "ghee" -> KEEP: Pure Desi Ghee, Cow Ghee, Buffalo Ghee, Danedar Ghee.
              REJECT: Ghee Roast Masala Paste, Ghee Diyas / Wicks (Pooja items).

• Personal Care & Household:
  - "soap" -> KEEP: Bathing Soap bars, Body Wash bars, Antibacterial Soap.
              REJECT: Soap Dish / Holder, Dishwashing Soap Bar / Vim Bar.
  - "shampoo" -> KEEP: Hair Shampoo (Anti-dandruff, Daily care, etc.).
                 REJECT: Shampoo Comb / Brush, Pet / Dog Shampoo.

============================================================
UNIVERSAL GENERALIZATION RULE:
============================================================
Even if the user's specific query is NOT in the benchmark list above (e.g. "poha", "besan", "honey", "ketchup", "biscuits", "detergent", "dry fruits"),
APPLY THE EXACT SAME 4 PRINCIPLES:
1. Is it the actual thing the user wants, or just a derivative / flavored snack / ingredient?
2. Is it a food/consumable rather than a tool/utensil/appliance?
3. Is it in the correct category rather than an accidental keyword collision?
4. Is it a genuine variant (size, brand, organic, type)?

============================================================
ANTI-HALLUCINATION & STRICT COVERAGE:
============================================================
- Every single product ID in the candidate list MUST be placed into either `relevant_ids` or `irrelevant_ids`.
- Never fabricate, alter, or omit product IDs. Only use IDs from the provided candidate text.
"""


class SemanticRelevanceFilter:
    """
    LLM-powered semantic bouncer that uses Groq (Llama 3) to filter out off-topic products.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.api_key = api_key or GROQ_API_KEY
        self.primary_model = primary_model or PRIMARY_MODEL
        self.fallback_model = fallback_model or FALLBACK_MODEL

        groq_key = SecretStr(self.api_key) if self.api_key else None

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_RELEVANCE_PROMPT),
            (
                "human",
                "User Search Query: \"{query}\"\n\nCandidate Products:\n{candidate_text}\n\nClassify every candidate product ID as relevant or irrelevant."
            )
        ])

        primary_llm = ChatGroq(
            model=self.primary_model,
            api_key=groq_key,
            temperature=0.0
        ).with_structured_output(RelevanceDecision)

        fallback_llm = ChatGroq(
            model=self.fallback_model,
            api_key=groq_key,
            temperature=0.0
        ).with_structured_output(RelevanceDecision)

        self.chain = self.prompt | primary_llm.with_fallbacks([fallback_llm])
        self.semaphore = asyncio.Semaphore(1)

    async def audit_relevance(
        self,
        products: List[RawProduct],
        search_query: str
    ) -> Tuple[List[RawProduct], int]:
        """
        Uses Groq LLM to semantically filter out irrelevant products.
        Returns: (relevant_products, irrelevant_dropped_count)
        """
        if not products:
            return [], 0

        if not self.api_key:
            # If no API key configured, pass through safely
            return products, 0

        # Audit top 10 candidate products to stay well within token limits and optimize latency
        audit_pool = products[:10]
        candidate_lines = [
            f"[ID: {p.id}] {p.name} ({p.brand or 'No Brand'})"
            for p in audit_pool
        ]
        candidate_text = "\n".join(candidate_lines)

        try:
            async with self.semaphore:
                raw_decision = await self.chain.ainvoke({
                    "query": search_query,
                    "candidate_text": candidate_text
                })

            if isinstance(raw_decision, dict):
                decision = RelevanceDecision.model_validate(raw_decision)
            else:
                decision = cast(RelevanceDecision, raw_decision)

            relevant_id_set = set(str(rid).strip() for rid in decision.relevant_ids)
            irrelevant_id_set = set(str(iid).strip() for iid in decision.irrelevant_ids)

            kept = []
            dropped_count = 0

            for p in products:
                p_id = str(p.id).strip()
                if p_id in relevant_id_set:
                    kept.append(p)
                elif p_id in irrelevant_id_set:
                    dropped_count += 1
                else:
                    # If LLM omitted an ID, default to keeping it for safety
                    kept.append(p)

            return kept, dropped_count

        except Exception as e:
            # Fallback gracefully so a network glitch never crashes search
            print(f"[WARN] Semantic filter exception: {e}. Falling back to original products.")
            return products, 0


# Global singleton instance for high performance
_FILTER_INSTANCE: Optional[SemanticRelevanceFilter] = None


def _get_filter() -> SemanticRelevanceFilter:
    global _FILTER_INSTANCE
    if _FILTER_INSTANCE is None:
        _FILTER_INSTANCE = SemanticRelevanceFilter()
    return _FILTER_INSTANCE


async def filter_relevance(
    products: List[RawProduct],
    search_query: str
) -> Tuple[List[RawProduct], int, int, int]:
    """
    Full 3-stage cleaning pipeline:
      1. Drop sponsored ads (is_ad == True)
      2. Drop out-of-stock items (available == False or inventory <= 0)
      3. Use Groq LLM Semantic Auditor to drop 'crows among pigeons' (books, utensils, cross-sells)

    Returns:
      (cleaned_products, ads_dropped, oos_dropped, irrelevant_dropped)
    """
    ads_dropped = 0
    oos_dropped = 0

    survivors: List[RawProduct] = []

    for p in products:
        # Step 1: Drop Ads
        if p.is_ad:
            ads_dropped += 1
            continue

        # Step 2: Drop Out of Stock
        if not p.available or (p.inventory is not None and p.inventory <= 0):
            oos_dropped += 1
            continue

        survivors.append(p)

    # Step 3: LLM Semantic Bouncer
    relevance_filter = _get_filter()
    cleaned, irrelevant_dropped = await relevance_filter.audit_relevance(
        products=survivors,
        search_query=search_query
    )

    return cleaned, ads_dropped, oos_dropped, irrelevant_dropped
