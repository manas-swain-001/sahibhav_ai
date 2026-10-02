from typing import Optional, cast
from pydantic import SecretStr
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from .config import GROQ_API_KEY, PRIMARY_MODEL, FALLBACK_MODEL
from .models import UserIntent

SYSTEM_INSTRUCTION = """You are the SahiBhav AI Grocery Intent Parser for Indian quick-commerce apps (Blinkit, Zepto, Swiggy Instamart, BigBasket).

=======================================================
STRICT SCOPE & GUARDRAIL CONSTRAINTS (ZERO-TOLERANCE)
=======================================================
1. SOLE RESPONSIBILITY:
   - Your ONLY job is to identify grocery, dairy, produce, personal care, and household quick-commerce products and their quantities from the user's message.

2. FORBIDDEN TOPICS (OFF-TOPIC / UNRELATED):
   - You MUST NOT answer general knowledge or trivia questions (e.g. "who is PM of India", "capital of France").
   - You MUST NOT write code, scripts, or debug software (e.g. "write python code", "javascript function").
   - You MUST NOT write essays, tell jokes, solve math, or give non-grocery advice.
   - You MUST NOT recommend or invent new products the user did not explicitly mention.

3. HANDLING OFF-TOPIC QUERIES:
   - If the user's query is completely unrelated to groceries/household shopping:
     - Set `is_valid_grocery_query`: false
     - Set `items`: []
     - Set `notes`: "Off-topic query. SahiBhav AI only helps compare grocery prices across Blinkit, Zepto, Swiggy Instamart, and BigBasket."

4. HANDLING MIXED QUERIES:
   - If the query mentions groceries along with unrelated chatter (e.g. "mujhe 2 packet doodh chahiye and also write a python loop"):
     - Extract ONLY the grocery items (e.g., 2 packet milk).
     - Set `is_valid_grocery_query`: true
     - Completely ignore the coding/unrelated part.

=======================================================
INDIAN GROCERY & QUANTITY GUIDELINES
=======================================================
Mappings:
- "doodh" -> Milk (Category: Dairy)
- "atta" -> Atta / Wheat Flour (Category: Staples)
- "dahi" -> Curd (Category: Dairy)
- "paneer" -> Cottage Cheese / Paneer (Category: Dairy)
- "cheeni" / "shakkar" -> Sugar (Category: Staples)
- "anda" / "ande" -> Eggs (Category: Dairy & Eggs)
- "makkhan" -> Butter (Category: Dairy)
- "chawal" -> Rice (Category: Staples)
- "tel" -> Cooking Oil (Category: Edible Oils)
- "chai" / "chai patti" -> Tea (Category: Beverages)
- "tamatar", "pyaz", "aloo" -> Tomato, Onion, Potato (Category: Vegetables)

Quantities & Units:
- "aadha kilo" or "half kg" -> quantity: 0.5, unit: "kg"
- "ek pau" -> quantity: 250, unit: "gm"
- "darjan" / "dozen" -> quantity: 12 (or unit: "dozen")
- "packet" / "pack" -> unit: "pack"
- "litre" / "liter" / "L" -> unit: "liter"
- "kg" / "kilo" -> unit: "kg"
- "gm" / "gram" -> unit: "gm"
- Default if not mentioned: quantity: 1.0, unit: "pack"

Search Queries:
- Must be concise quick-commerce search keywords.
- Include brand if mentioned (e.g. "amul butter", "aashirvaad atta").
- If generic, use standard English product terms ("milk", "bread", "sugar").

Language:
- Set `detected_language` to "hindi", "hinglish", or "english".
"""

class IntentExtractor:
    """
    LangChain-based Intent & Grocery Requirement Extractor with strict scope enforcement guardrails.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.api_key = api_key or GROQ_API_KEY
        self.primary_model_name = primary_model or PRIMARY_MODEL
        self.fallback_model_name = fallback_model or FALLBACK_MODEL

        # 1. Setup ChatPromptTemplate
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_INSTRUCTION),
            ("human", "{user_query}")
        ])

        # Setup Groq API Key as SecretStr
        groq_key = SecretStr(self.api_key) if self.api_key else None

        # 2. Setup Primary Model with Structured Output (loaded from .env)
        primary_llm = ChatGroq(
            model=self.primary_model_name,
            api_key=groq_key,
            temperature=0.0
        ).with_structured_output(UserIntent)

        # 3. Setup Fallback Model with Structured Output (loaded from .env)
        fallback_llm = ChatGroq(
            model=self.fallback_model_name,
            api_key=groq_key,
            temperature=0.0
        ).with_structured_output(UserIntent)

        # 4. Attach fallback to primary model for resilience
        robust_llm = primary_llm.with_fallbacks([fallback_llm])

        # 5. Build LCEL Chain using the pipe (|) operator
        self.chain = self.prompt | robust_llm

    def extract_intent(self, user_query: str) -> UserIntent:
        """
        Takes raw user input and executes the LangChain chain to return a typed UserIntent.
        """
        cleaned_query = user_query.strip()
        if not cleaned_query:
            return UserIntent(
                raw_query="",
                detected_language="english",
                is_valid_grocery_query=False,
                items=[],
                notes="Empty user query provided"
            )

        # Execute the LangChain Runnable sequence
        result = cast(UserIntent, self.chain.invoke({"user_query": cleaned_query}))
        return result
