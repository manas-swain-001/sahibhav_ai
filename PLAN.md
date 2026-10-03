# SahiBhav AI — Master Plan

> Project: AI agent that finds the best 2-platform combo across Indian quick-commerce apps.
> Tagline: *Har platform, sahi bhav.*
> Repo: sahibhav-ai (backend) + sahibhav-web (frontend)

---

## 1. ARCHITECTURE

React Frontend (browser)
        ↓ HTTP POST /api/recommend
FastAPI Backend (Python, thin wrapper)
        ↓
Core Pipeline (Python)
   ├── Stage 1: Intent Extraction (LLM)
   ├── Stage 2: Search 4 platforms (Python)
   ├── Stage 3: Optimizer (Python)
   └── Stage 4: Response Generation (LLM)
        ↓
External APIs
   ├── QuickCommerce API (product search)
   └── Groq (LLM for Stages 1 & 4)

---

## 2. BUILD STEPS

### BACKEND (Today)
1.  ✅ Project init with uv
2.  ✅ Config + Groq key
3.  ⏳ Pydantic models           → src/models.py
4.  ⏳ QuickCommerce client      → src/client/qc_client.py
5.  ⏳ Data cleaning tools       → src/tools/*.py
6.  ⏳ Product normalizer        → src/tools/normalizer.py
7.  ⏳ Stage 1: Intent (LLM)     → src/stages/intent.py
8.  ⏳ Stage 2: Search (Python)  → src/stages/search.py
9.  ⏳ Stage 3: Optimizer        → src/stages/optimizer.py
10. ⏳ Stage 4: Responder (LLM)  → src/stages/responder.py
11. ⏳ Pipeline orchestrator     → src/pipeline.py
12. ⏳ CLI test                  → cli.py

### FASTAPI + REACT (Tomorrow)
13. ⏳ FastAPI app + endpoint    → api/main.py
14. ⏳ CORS setup
15. ⏳ Test endpoint with curl
16. ⏳ Vite + React + Tailwind
17. ⏳ Chat input component
18. ⏳ API call to backend
19. ⏳ Results display cards
20. ⏳ Language toggle (Hindi/English)

### DEPLOY (Day 3)
21. ⏳ Deploy FastAPI → Render/Fly
22. ⏳ Deploy React → Vercel
23. ⏳ Env vars + CORS in prod
24. ⏳ LinkedIn post + demo video

---

## 3. PIPELINE FLOW (CORE LOGIC)

USER INPUT: "mujhe doodh aur atta chahiye"
   ↓
STAGE 1 — INTENT EXTRACTION (LLM)
   Input:  "mujhe doodh aur atta chahiye"
   Output: { language: "hinglish", products: ["milk", "atta"] }
   ↓
STAGE 2 — SEARCH (Python)
   For each product, call qc_client on 4 platforms:
     • BlinkIt
     • Zepto
     • Swiggy
     • BigBasket
   Then: filter ads + OOS + irrelevant, dedupe Swiggy,
         parse quantity, compute price_per_500ml
   ↓
STAGE 3 — OPTIMIZER (Python)
   • Try all 2-platform combinations
   • Score: 70% price (offer_price/standard_price) + 25% ETA + 5% rating (default 4.0★ if null)
   • Pick best combo
   Output: { platform_1, platform_2, total, savings }
   ↓
STAGE 4 — RESPONDER (LLM)
   Input:  structured recommendation + language
   Output: "Bhai, sabse sahi deal ye hai: ..."
   ↓
RESPONSE (JSON) → FastAPI → React

---

## 4. FOLDER STRUCTURE

sahibhav-ai/                     ← Python backend
├── src/
│   ├── config.py                ✅ done
│   ├── models.py                Step 3
│   ├── client/
│   │   └── qc_client.py         Step 4
│   ├── tools/
│   │   ├── quantity_parser.py   Step 5
│   │   ├── eta_parser.py        Step 5
│   │   ├── dedupe.py            Step 5
│   │   ├── relevance.py         Step 5
│   │   ├── pricing.py           Step 5
│   │   └── normalizer.py        Step 6
│   └── stages/
│       ├── intent.py            Step 7
│       ├── search.py            Step 8
│       ├── optimizer.py         Step 9
│       └── responder.py         Step 10
├── api/
│   └── main.py                  Step 11 (FastAPI Backend)
├── data/
│   ├── fixtures/
│   └── unhandled_quantities.log
├── .env                         ✅ done
├── pyproject.toml               ✅ done
└── README.md

sahibhav-web/                    ← React frontend (tomorrow)
├── src/
│   ├── App.tsx
│   └── components/
└── package.json

---

## 5. CONFIG SUMMARY

LLM:        Groq — llama-3.3-70b-versatile (1000 req/day free)
Temperature: 0.0 (deterministic)
QC API:     https://api.quickcommerceapi.com/v1/search
Auth:       X-API-Key header
Platforms:  BlinkIt, Zepto, Swiggy, BigBasket
Demo location: 12.9122, 77.6407 (HSR Layout, Bangalore)
Pricing rule: 70% price (using offer_price & standard unit) + 25% ETA + 5% rating (default 4.0★ if null)
Max platforms per recommendation: 2

.env keys:
  QUICKCOMMERCE_API_KEY=...
  GROQ_API_KEY=gsk_...

---

## 6. API RESEARCH — KEY FACTS

### Schema quirks (from real tests)
- mrp/offer_price types: BlinkIt=int, BigBasket=str, Swiggy=str, Zepto=float
- rating: BigBasket=null, others=real
- inventory: BigBasket & Swiggy always fake (1)
- store_id: BlinkIt=int, BigBasket=str, Swiggy=str, Zepto=UUID
- is_ad: present in individual search, MISSING in group search
- ETA format: "X mins" everywhere (consistent ✅)

### Must-filter rules
1. is_ad == true             → drop (sponsored)
2. available == false        → drop (OOS)
3. inventory == 0            → drop (belt & suspenders)
4. Duplicate product_id      → Swiggy: keep smallest pack
5. Irrelevant results        → keyword filter on "milk", "doodh"
   Blacklist: chocolate, biscuit, bread, soap, pan, cookies,
              shake, cake, coffee, powder, whitener, condensed

### Quantity formats to parse
"500 ml", "1 ltr", "1 L", "200 ml", "450 ml",
"1 pack (500 ml)", "1 pc (500 ml)", "475 ml or 500 ml",
"2 x 60 g + 60 g", "5 x 65 ml", "1 ltr x 4", "500 ml x 2"

### Real arbitrage example (Bhubaneswar test)
Amul Taaza Toned Milk 500ml:
  Swiggy=₹27 | Blinkit=₹29 | BigBasket=₹40
→ ₹13 difference — this is why the project exists.

### Location behavior
Bhubaneswar brands: Omfed, Pragati, Milky Moo, Mother Dairy
Bangalore brands:   Nandini, Heritage, Arokya, Akshayakalpa
→ Same "milk" query returns different brands by city.

---

## 7. DESIGN DECISIONS (LOCKED)

1.  Use individual /v1/search (4 parallel calls), not group search
2.  Pydantic with field_validator for type coercion
3.  Round ratings to 1 decimal (Blinkit float32 bug)
4.  Optional[float] for rating (BigBasket returns null)
5.  Ignore inventory except on BlinkIt/Zepto
6.  Filter is_ad == true
7.  Filter available == false
8.  Dedupe Swiggy by product_id (smallest pack)
9.  Relevance filter: keyword + blacklist
10. Quantity parser → (unit, amount)
11. Compute price per 500ml/kg for fair comparison
12. store_id: Union[int, str]
13. ETA parser: "12 mins" → 12
14. Region-aware (lat/lon passed per request)
15. Single pipeline, not multi-agent (LLM only at Stages 1 & 4)

---

## 8. STACK

Language:     Python 3.11
Package mgr:  uv
HTTP:         httpx
Validation:   pydantic
Env:          python-dotenv
LLM:          langchain + langchain-groq
API layer:    FastAPI (later today/tomorrow)
Frontend:     React + Vite + Tailwind (tomorrow)
Deploy:       Render (backend) + Vercel (frontend)

---

## 9. CURRENCY

Credits remaining (QC API): ~89
Credits used so far:        ~11
Cost per full user query:   4 (1 per platform)
Demo budget:                plenty left

---

## 10. NEXT ACTION

→ Step 3: Write src/models.py
  Verify Step 2 first:
    uv run python scripts/test_config.py