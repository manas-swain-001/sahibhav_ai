# 🐍 Complete Python Handbook for JavaScript/TypeScript Engineers
### *Mastering Python & FastAPI through the SahiBhav AI Codebase*

> **Context:** If you are excellent in JavaScript/TypeScript (Node.js, Express, React, Zod, Axios, Promises), this handbook maps every Python pattern, idiom, and library used in this repository directly to its JavaScript equivalent.

---

## 📑 Table of Contents
1. [Core Language & Data Types Side-by-Side](#1-core-language--data-types-side-by-side)
2. [FastAPI vs. Express.js / Fastify (`server/api/main.py`)](#2-fastapi-vs-expressjs--fastify-serverapimainpy)
3. [Environment & Config (`server/src/sahibhav_ai/config.py`)](#3-environment--config-serversrcsahibhav_aiconfigpy)
4. [Data Validation: Pydantic vs. Zod (`server/src/sahibhav_ai/models.py`)](#4-data-validation-pydantic-vs-zod-serversrcsahibhav_aimodelspy)
5. [HTTP Client & Async Concurrency (`server/src/sahibhav_ai/client/qc_client.py`)](#5-http-client--async-concurrency-serversrcsahibhav_aiclientqc_clientpy)
6. [Rate-Limiting & Semaphores: `asyncio.Semaphore` vs. `p-limit` (`relevance.py`)](#6-rate-limiting--semaphores-asyncio-semaphore-vs-p-limit-relevancepy)
7. [Regex & Text Parsing (`quantity_parser.py` & `eta_parser.py`)](#7-regex--text-parsing-quantity_parserpy--eta_parserpy)
8. [Array Methods: Comprehensions vs. `map`, `filter`, `reduce` (`search.py`, `optimizer.py`)](#8-array-methods-comprehensions-vs-map-filter-reduce-searchpy-optimizerpy)
9. [Sorting & Combinatorics: `itertools` & `max(..., key=lambda)` (`optimizer.py`)](#9-sorting--combinatorics-itertools--max-keylambda-optimizerpy)
10. [LLM Structured Output: LangChain vs. Vercel AI SDK (`intent_extractor.py`, `responder.py`)](#10-llm-structured-output-langchain-vs-vercel-ai-sdk-intent_extractorpy-responderpy)
11. [Floating Point Rounding Gotcha: Python `round()` vs. JS `Math.round()`](#11-floating-point-rounding-gotcha-python-round-vs-js-mathround)
12. [Project Architecture: `pyproject.toml` & `__init__.py` vs. `package.json` & `index.ts`](#12-project-architecture-pyprojecttoml--__init__py-vs-packagejson--indexts)

---

## 1. Core Language & Data Types Side-by-Side

| Concept | Python | JavaScript / TypeScript | Why Python Does It This Way |
| :--- | :--- | :--- | :--- |
| **Integers vs Floats** | `int` (`10`) & `float` (`10.5`) | `number` (IEEE 754 float) | Python has true integers with arbitrary precision (never overflows). |
| **Booleans** | `True`, `False` | `true`, `false` | Python booleans must be **Capitalized**. |
| **Null Value** | `None` | `null` / `undefined` | Python has **only one** representation of emptiness (`None`). No `undefined` vs `null` debate. |
| **Template Strings** | `f"Item: {name}, ₹{price:.2f}"` | `` `Item: ${name}, ₹${price.toFixed(2)}` `` | Python uses `f"..."` (formatted strings). Formatting specs like `:.2f` are built right in. |
| **Array / List** | `items = [1, 2]`<br>`items.append(3)` | `const items = [1, 2];`<br>`items.push(3);` | Methods: `.append()` (push), `.pop()`, `.extend()` (concat in place). |
| **Array Length** | `len(items)` | `items.length` | Python uses universal `len()` built-in function instead of properties. |
| **Object / Hash Map** | `d = {"a": 1}`<br>`d["a"]` or `d.get("a", default)` | `const d = { a: 1 };`<br>`d.a` or `d["a"]` | Python `dict` keys can be any hashable type (strings, ints, tuples). **No dot-notation** for plain dicts. |
| **Spread Operator** | `*list` (args), `**dict` (kwargs) | `...array`, `{ ...object }` | `*` unpacks sequences into positional args; `**` unpacks mappings into keyword args. |
| **Negative Indexing** | `arr[-1]` (last), `arr[-2]` | `arr.at(-1)` or `arr[arr.length - 1]` | Built-in negative indices count backwards from the end. |
| **Slice Syntax** | `arr[1:4]`, `arr[:10]` | `arr.slice(1, 4)`, `arr.slice(0, 10)` | Built-in slicing returns new shallow copy. |
| **Logical Operators** | `and`, `or`, `not` | `&&`, `||`, `!` | English words instead of symbolic tokens. |
| **Truthy / Falsy** | `[]`, `{}`, `""`, `0`, `None` are `False` | `[]` and `{}` are **`true`**! | In Python, empty collections `[]` and `{}` are **falsy**! In JS, `[] == false` but `Boolean([]) === true`. |

---

## 2. FastAPI vs. Express.js / Fastify (`server/api/main.py`)

FastAPI is the modern standard in Python for building microservices, APIs, and AI backends. Here is how it directly translates to Express.js / Fastify:

### A. Server Initialization & CORS

```python
# 🐍 Python (FastAPI) - server/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SahiBhav AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```javascript
// 🟨 JavaScript (Express.js)
import express from "express";
import cors from "cors";

const app = express();
app.use(express.json());

app.use(cors({
  origin: "*",
  credentials: true,
  methods: ["*"],
  allowedHeaders: ["*"],
}));
```

---

### B. Route Definitions & Automatic Type Validation

In Express, you manually parse `req.body` with Zod. In FastAPI, **typing the parameter with a Pydantic model automatically validates the request body**:

```python
# 🐍 Python (FastAPI)
from pydantic import BaseModel, Field

class OptimizeRequest(BaseModel):
    query: str
    lat: float = 20.31
    lon: float = 85.88

@app.post("/api/optimize", response_model=SahiBhavResponse)
async def optimize(req: OptimizeRequest):
    # req is ALREADY validated, parsed, and typed!
    # If the client sends invalid types, FastAPI automatically returns 422 Unprocessable Entity!
    query = req.query
    return await run_pipeline(query, req.lat, req.lon)
```

```typescript
// 🟨 TypeScript (Express + Zod)
import { Request, Response } from "express";
import { z } from "zod";

const OptimizeRequestSchema = z.object({
  query: z.string(),
  lat: z.number().default(20.31),
  lon: z.number().default(85.88),
});

app.post("/api/optimize", async (req: Request, res: Response) => {
  // Manual validation step needed in Express:
  const parseResult = OptimizeRequestSchema.safeParse(req.body);
  if (!parseResult.success) {
    return res.status(422).json({ error: parseResult.error });
  }

  const { query, lat, lon } = parseResult.data;
  const result = await runPipeline(query, lat, lon);
  return res.json(result);
});
```

---

### C. Throwing Errors: `HTTPException` vs. `res.status().json()`

```python
# 🐍 Python (FastAPI)
from fastapi import HTTPException

if not query.strip():
    raise HTTPException(status_code=400, detail="Query cannot be empty.")
```

```javascript
// 🟨 JavaScript (Express.js)
if (!query.trim()) {
    return res.status(400).json({ detail: "Query cannot be empty." });
}
```

---

### D. Free Interactive Swagger Documentation

* In **Express**: You have to install `swagger-ui-express`, write manual YAML/JSDoc annotations, and maintain it manually.
* In **FastAPI**: It is **100% automatic**. Navigating to `http://localhost:8000/docs` gives you a live, interactive Swagger UI generated directly from your Pydantic models.

---

## 3. Environment & Config (`server/src/sahibhav_ai/config.py`)

```python
# 🐍 Python - server/src/sahibhav_ai/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Pathlib: Modern object-oriented filesystem paths
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "20.31"))
SUPPORTED_PLATFORMS = ["BlinkIt", "Zepto", "Swiggy", "BigBasket"]

if not GROQ_API_KEY:
    raise ValueError(f"GROQ_API_KEY not found at {ENV_PATH}")
```

```javascript
// 🟨 JavaScript (Node.js ESM)
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const envPath = path.resolve(__dirname, "../../..", ".env");
dotenv.config({ path: envPath });

export const GROQ_API_KEY = process.env.GROQ_API_KEY ?? "";
export const DEFAULT_LAT = parseFloat(process.env.DEFAULT_LAT ?? "20.31");
export const SUPPORTED_PLATFORMS = ["BlinkIt", "Zepto", "Swiggy", "BigBasket"];

if (!GROQ_API_KEY) {
  throw new Error(`GROQ_API_KEY not found at ${envPath}`);
}
```

---

## 4. Data Validation: Pydantic vs. Zod (`server/src/sahibhav_ai/models.py`)

Pydantic in Python plays the exact same role as **Zod + TypeScript interfaces** in JavaScript:

```python
# 🐍 Python (Pydantic v2) - server/src/sahibhav_ai/models.py
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class RawProduct(BaseModel):
    id: str
    name: str
    mrp: float = 0.0
    offer_price: float = 0.0
    rating: Optional[float] = None
    images: List[str] = Field(default_factory=list)

    # Pre-validation hook (cleans dirty API types before validation)
    @field_validator("offer_price", mode="before")
    @classmethod
    def coerce_price(cls, v):
        if v is None or v == "":
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0
```

```typescript
// 🟨 TypeScript (Zod Equivalent)
import { z } from "zod";

export const RawProductSchema = z.object({
  id: z.string(),
  name: z.string(),
  mrp: z.number().default(0.0),
  // z.preprocess is equivalent to @field_validator(mode="before"):
  offer_price: z.preprocess((val) => {
    if (val === null || val === undefined || val === "") return 0.0;
    const num = parseFloat(String(val));
    return isNaN(num) ? 0.0 : num;
  }, z.number().default(0.0)),
  rating: z.number().nullable().optional(),
  images: z.array(z.string()).default([]),
});

export type RawProduct = z.infer<typeof RawProductSchema>;
```

---

## 5. HTTP Client & Async Concurrency (`server/src/sahibhav_ai/client/qc_client.py`)

### A. Context Manager `async with` vs. `try...finally`

Python uses `async with httpx.AsyncClient() as client:` to guarantee connection pooling and socket cleanup:

```python
# 🐍 Python (HTTPX)
async with httpx.AsyncClient(timeout=15.0) as client:
    resp = await client.get(self.base_url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json()
```

```javascript
// 🟨 JavaScript (Axios / Fetch)
// In Node.js, fetch / axios handles pooling under the hood:
const resp = await axios.get(this.baseUrl, {
  headers,
  params,
  timeout: 15000,
});
const data = resp.data;
```

---

### B. Parallel API Calls: `asyncio.gather` vs. `Promise.all`

```python
# 🐍 Python
tasks = [
    self.search_platform(platform=p, query=query)
    for p in target_platforms
]
# return_exceptions=True prevents one failed platform from crashing the others!
results = await asyncio.gather(*tasks, return_exceptions=True)
```

```javascript
// 🟨 JavaScript
const tasks = target_platforms.map(p =>
  this.searchPlatform(p, query)
);
// Promise.allSettled guarantees all promises complete even if one rejects:
const results = await Promise.allSettled(tasks);
```

---

## 6. Rate-Limiting & Semaphores: `asyncio.Semaphore` vs. `p-limit` (`relevance.py`)

When calling LLM APIs (like Groq) concurrently, firing 8 calls at once can trigger **HTTP 429 Rate Limit Exceeded**. 

A **Semaphore** limits how many async tasks can execute simultaneously:

```python
# 🐍 Python - server/src/sahibhav_ai/tools/relevance.py
import asyncio

class SemanticRelevanceFilter:
    def __init__(self):
        # Only allow 1 request to hit Groq at any given moment
        self.semaphore = asyncio.Semaphore(1)

    async def audit_relevance(self, products, query):
        async with self.semaphore:
            # Code inside this block is guaranteed to run exclusively
            return await self.chain.ainvoke({"query": query, ...})
```

```javascript
// 🟨 JavaScript (p-limit npm package)
import pLimit from "p-limit";

class SemanticRelevanceFilter {
  constructor() {
    // Concurrency limit: 1
    this.limit = pLimit(1);
  }

  async auditRelevance(products, query) {
    return this.limit(async () => {
      // Runs at most 1 at a time
      return await this.chain.invoke({ query, ... });
    });
  }
}
```

---

## 7. Regex & Text Parsing (`quantity_parser.py` & `eta_parser.py`)

Parsing complex strings like `"2 x 60 g + 60 g"` or `"12 mins"`:

```python
# 🐍 Python - re module
import re

# Match pattern: digits followed by word
match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', text)
if match:
    val = float(match.group(1))   # Group 1 (amount)
    unit = match.group(2)         # Group 2 (unit)
```

```javascript
// 🟨 JavaScript - RegExp
const regex = /(\d+(?:\.\d+)?)\s*([a-zA-Z]+)/;
const match = text.match(regex);
if (match) {
  const val = parseFloat(match[1]); // Group 1
  const unit = match[2];            // Group 2
}
```

---

## 8. Array Methods: Comprehensions vs. `map`, `filter`, `reduce` (`search.py`, `optimizer.py`)

Python developers heavily favor **List Comprehensions** over `.map()` and `.filter()`:

### A. Filter + Map in One Line

```python
# 🐍 Python List Comprehension
valid_prices = [
    p.offer_price
    for p in all_products
    if p.offer_price > 0
]
```

```javascript
// 🟨 JavaScript Chain
const validPrices = allProducts
  .filter(p => p.offerPrice > 0)
  .map(p => p.offerPrice);
```

---

### B. Checking Conditions: `all()` and `any()`

```python
# 🐍 Python
# Check if a platform has every item in the cart:
has_all_items = all(plat in plat_map for plat_map in best_picks_by_item)

# Check if at least one platform can cover the item:
can_cover = any(p in plat_map for p in candidate_platforms)
```

```javascript
// 🟨 JavaScript: .every() and .some()
const hasAllItems = bestPicksByItem.every(platMap => plat in platMap);

const canCover = candidatePlatforms.some(p => p in platMap);
```

---

### C. Calculating Sums: `sum()` vs. `.reduce()`

```python
# 🐍 Python
subtotal = round(sum(x.item_total_price for x in order_picks), 2)
```

```javascript
// 🟨 JavaScript
const subtotal = Math.round(
  orderPicks.reduce((acc, x) => acc + x.itemTotalPrice, 0) * 100
) / 100;
```

---

## 9. Sorting & Combinatorics: `itertools` & `max(..., key=lambda)` (`optimizer.py`)

### A. All 2-Platform Pairings: `itertools.combinations`

```python
# 🐍 Python
import itertools

platforms = ["blinkit", "zepto", "swiggy", "bigbasket"]
# Generates all pairs: ('blinkit', 'zepto'), ('blinkit', 'swiggy'), ...
for p1, p2 in itertools.combinations(sorted(platforms), 2):
    ...
```

```javascript
// 🟨 JavaScript (requires nested loops)
const platforms = ["bigbasket", "blinkit", "swiggy", "zepto"].sort();
for (let i = 0; i < platforms.length; i++) {
  for (let j = i + 1; j < platforms.length; j++) {
    const p1 = platforms[i];
    const p2 = platforms[j];
    // ...
  }
}
```

---

### B. Finding the Best Item: `max()` with Multi-Criteria Tuple

```python
# 🐍 Python
# Sort primarily by composite score (highest first), break ties with price (cheapest first)
best_prod = max(products, key=lambda x: (x.score, -x.offer_price))
```

```javascript
// 🟨 JavaScript (requires .sort or custom reduce)
const bestProd = products.slice().sort((a, b) => {
  if (b.score !== a.score) {
    return b.score - a.score; // Highest score first
  }
  return a.offerPrice - b.offerPrice; // Lowest price first
})[0];
```

---

## 10. LLM Structured Output: LangChain vs. Vercel AI SDK (`intent_extractor.py`, `responder.py`)

### A. Extracting Typed JSON from an LLM

```python
# 🐍 Python (LangChain Groq + Pydantic)
from langchain_groq import ChatGroq
from .models import UserIntent

llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0.0)
structured_extractor = llm.with_structured_output(UserIntent)

result: UserIntent = structured_extractor.invoke("1 packet milk chahiye")
# result is an instantiated UserIntent Pydantic object!
```

```typescript
// 🟨 TypeScript (Vercel AI SDK + Zod)
import { generateObject } from "ai";
import { groq } from "@ai-sdk/groq";
import { UserIntentSchema } from "./models";

const { object } = await generateObject({
  model: groq("openai/gpt-oss-20b"),
  schema: UserIntentSchema,
  prompt: "1 packet milk chahiye",
});
// object is a validated TypeScript UserIntent!
```

---

## 11. Floating Point Rounding Gotcha: Python `round()` vs. JS `Math.round()`

> ⚠️ **CRITICAL DIFFERENCE:** Python uses **Banker's Rounding** (round half to even), whereas JavaScript uses **Round Half Away from Zero** (round half up).

```python
# 🐍 Python
round(2.5)  # -> 2  (rounds to closest EVEN number!)
round(3.5)  # -> 4  (rounds to closest EVEN number!)
```

```javascript
// 🟨 JavaScript
Math.round(2.5)  // -> 3  (rounds UP!)
Math.round(3.5)  // -> 4  (rounds UP!)
```

In finance and e-commerce pricing, Banker's Rounding is mathematically preferred because it prevents upward statistical inflation over thousands of transactions!

---

## 12. Project Architecture: `pyproject.toml` & `__init__.py` vs. `package.json` & `index.ts`

### A. Package Manifest Comparison

| Role | Python Ecosystem | JavaScript / Node.js |
| :--- | :--- | :--- |
| **Package Manifest** | `pyproject.toml` | `package.json` |
| **Lockfile** | `uv.lock` | `package-lock.json` or `pnpm-lock.yaml` |
| **Package Manager** | `uv` (Ultra-fast Rust package manager) | `npm` / `pnpm` / `bun` |
| **Dependencies Folder** | `.venv/Lib/site-packages` | `node_modules` |
| **Run Script** | `uv run python script.py` | `npx tsx script.ts` / `npm run ...` |

---

### B. What is `__init__.py`?

In Python, any folder containing an `__init__.py` file is treated as an **importable package** (equivalent to an `index.ts` or `index.js` in a folder):

```python
# 🐍 Python - server/src/sahibhav_ai/stages/__init__.py
from .search import MultiItemSearchStage
from .optimizer import ComboOptimizer
from .responder import AIResponderStage

__all__ = ["MultiItemSearchStage", "ComboOptimizer", "AIResponderStage"]
```

```typescript
// 🟨 TypeScript - server/src/sahibhav_ai/stages/index.ts
export { MultiItemSearchStage } from "./search";
export { ComboOptimizer } from "./optimizer";
export { AIResponderStage } from "./responder";
```

Now, outside callers can simply write:
```python
# Python
from sahibhav_ai.stages import ComboOptimizer
```
instead of importing from internal deep paths!

---

### C. What is `if __name__ == "__main__":`?

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
```

In Python, every file has a built-in variable `__name__`:
- When you execute the file directly (`python api/main.py`), `__name__` equals `"__main__"`. The server starts!
- When another file imports it (`from api.main import app`), `__name__` equals `"api.main"`. The code inside the `if` block **does NOT run**!

**JavaScript Equivalent (ESM):**
```javascript
import { fileURLToPath } from "url";

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  // Executed directly from terminal
  app.listen(8000);
}
```

---

### 🚀 Summary: Translating Your JS Superpowers to Python

1. **FastAPI is Express + Zod + Swagger in a single unified framework.**
2. **Pydantic is Zod**, validating and coercing types automatically.
3. **`asyncio.gather` is `Promise.all`**, running concurrent requests across quick-commerce apps.
4. **List comprehensions replace `.map().filter()`**, making data transformations concise and expressive.
5. **`uv` is your new `npm`**, installing and running Python packages with sub-second speeds.
