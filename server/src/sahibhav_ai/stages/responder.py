from typing import Optional, Dict, Any, cast
import json
from pydantic import SecretStr
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from ..config import GROQ_API_KEY, PRIMARY_MODEL, FALLBACK_MODEL
from ..models import OptimizationResult, SahiBhavResponse

RESPONDER_SYSTEM_INSTRUCTION = """You are "SahiBhav AI" (सही भाव AI) — India's smartest quick-commerce shopping companion.
You help users save real money when shopping across Blinkit, Zepto, Swiggy Instamart, and BigBasket.

=======================================================
CRITICAL MULTILINGUAL INSTRUCTION (ALL LANGUAGES)
=======================================================
- SahiBhav AI supports ALL languages and dialects globally and across India (Odia, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Hindi, Hinglish, English, Bhojpuri, Urdu, Spanish, French, etc.).
- ALWAYS respond in the EXACT same language and script that the user used.
  - If the user wrote in Odia (e.g. "mote 1 packet khira au butter darkar"), reply in warm, colloquial Odia (e.g. Romanized Odia or Odia script depending on user style).
  - If the user wrote in Bengali, reply in Bengali.
  - If the user wrote in Hinglish, reply in friendly, conversational Hinglish ("Bhai, sabse best deal ye hai...").
  - If the user wrote in Tamil/Telugu/Kannada/Malayalam/Marathi, reply in that language.
  - If the user wrote in English, reply in clean, helpful English.
- Match the user's tone: friendly, witty, smart, transparent, like a trusted friend who knows all local grocery hacks.

=======================================================
CONTENT & RECOMMENDATION GUIDELINES
=======================================================
1. THE WINNING RECOMMENDATION:
   - Announce whether the best deal is a Single Platform (convenience) or a 2-Platform Split (maximum savings).
   - State the final total cost and the exact rupees saved.

2. DELIVERY FEE TRANSPARENCY:
   - Always mention delivery fee rules clearly:
     - Orders under ₹200 have a ₹30 delivery fee per platform.
     - Orders ₹200 and above get FREE delivery.
   - If recommending a 2-platform split, clearly state why the split is worth it even with any extra delivery charges.

3. ITEM & PLATFORM BREAKDOWN:
   - List which items to order from which platform.
   - Mention the estimated delivery time (ETA) for each platform.
   - Include the product names and prices.

4. OFF-TOPIC QUERIES:
   - If the input was marked invalid / off-topic, politely explain in the user's language that SahiBhav AI is exclusively focused on grocery price comparison, and ask them what groceries they'd like to find today.
"""

RESPONDER_HUMAN_TEMPLATE = """User Query: "{raw_query}"
Detected Language: {detected_language}
Optimization Data:
{optimization_json}

Provide a helpful, friendly, and structured response in {detected_language} guiding the user on the best way to buy their groceries.
"""


class AIResponderStage:
    """
    Stage 4: Multilingual Natural Language Responder powered by Groq LLM.
    Uses 0 QuickCommerce API credits (Groq only).
    Supports all regional and global languages.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
    ):
        self.api_key = api_key or GROQ_API_KEY
        self.model_name = model_name or PRIMARY_MODEL
        self.temperature = temperature

        self.primary_llm = ChatGroq(
            api_key=SecretStr(self.api_key),
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=1024,
        )

        self.fallback_llm = ChatGroq(
            api_key=SecretStr(self.api_key),
            model=FALLBACK_MODEL,
            temperature=self.temperature,
            max_tokens=1024,
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", RESPONDER_SYSTEM_INSTRUCTION),
            ("human", RESPONDER_HUMAN_TEMPLATE),
        ])

    def _prepare_optimization_summary(self, result: OptimizationResult) -> str:
        """Serializes key optimization metrics for the LLM prompt."""
        if not result.is_valid_grocery_query:
            return json.dumps({
                "is_valid_grocery_query": False,
                "notes": result.notes or "Query is not related to groceries."
            }, indent=2)

        winning = result.winning_recommendation
        summary: Dict[str, Any] = {
            "is_valid_grocery_query": True,
            "detected_language": result.detected_language,
            "recommended_strategy": winning.combo_type if winning else "single_platform",
            "platforms": winning.platforms if winning else [],
            "items_subtotal": winning.items_subtotal if winning else 0.0,
            "delivery_fees": winning.total_delivery_fees if winning else 0.0,
            "total_price": winning.total_price if winning else 0.0,
            "max_eta_mins": winning.max_eta_mins if winning else None,
            "savings_vs_highest": winning.savings_vs_highest if winning else 0.0,
            "savings_vs_best_single": winning.savings_vs_best_single if winning else 0.0,
            "orders": []
        }

        if winning:
            for order in winning.orders:
                order_info = {
                    "platform": order.platform,
                    "eta_mins": order.eta_mins,
                    "items_subtotal": order.items_subtotal,
                    "delivery_fee": order.delivery_fee,
                    "total_order_cost": order.total_order_cost,
                    "items": [
                        {
                            "requested": it.item_name,
                            "product_name": it.product.name,
                            "quantity": f"{it.quantity_requested} {it.unit_requested}",
                            "price": it.item_total_price,
                            "deeplink": it.product.deeplink,
                        }
                        for it in order.items
                    ]
                }
                summary["orders"].append(order_info)

        return json.dumps(summary, indent=2, ensure_ascii=False)

    def generate_response(
        self,
        raw_query: str,
        optimization_result: OptimizationResult,
        detected_language: Optional[str] = None,
    ) -> SahiBhavResponse:
        """
        Generates a natural language response in the user's detected language.
        """
        lang = detected_language or optimization_result.detected_language or "english"
        opt_json = self._prepare_optimization_summary(optimization_result)

        formatted_messages = self.prompt.format_messages(
            raw_query=raw_query,
            detected_language=lang,
            optimization_json=opt_json,
        )

        try:
            ai_msg = self.primary_llm.invoke(formatted_messages)
            text_response = str(ai_msg.content)
        except Exception:
            # Fallback to secondary model (e.g. llama-3.1-8b-instant)
            ai_msg = self.fallback_llm.invoke(formatted_messages)
            text_response = str(ai_msg.content)

        return SahiBhavResponse(
            raw_query=raw_query,
            detected_language=lang,
            is_valid_grocery_query=optimization_result.is_valid_grocery_query,
            natural_language_response=text_response,
            optimization=optimization_result,
            notes=optimization_result.notes,
        )
