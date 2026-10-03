# 🐍 Python Quick Learnings (with JavaScript Comparisons)

A fast, no-fluff handbook of real Python concepts learned while building **SahiBhav AI**, compared directly to JavaScript/TypeScript.

---

## 1. Data Types Side-by-Side

| Python | JavaScript / TypeScript | Python Example | JS Example | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`int` / `float`** | `number` | `x = 10`, `y = 10.5` | `let x = 10;` | Python separates ints and floats; JS only has `number`. |
| **`str`** | `string` | `s = f"₹{price}"` | `let s = \`₹${price}\`;` | Python uses `f"..."` for template literals. |
| **`bool`** | `boolean` | `is_valid = True` | `let isValid = true;` | Python booleans must be **Capitalized** (`True`, `False`). |
| **`None`** | `null` / `undefined` | `brand = None` | `let brand = null;` | Python only has `None` (no `undefined`). |
| **`list`** | `Array` | `items = ["a", "b"]` | `const items = ["a", "b"];` | Add item: Python `items.append("c")` vs JS `items.push("c")`. |
| **`tuple`** | `readonly Array` | `t = (500, "ml")` | `const t = Object.freeze([500, "ml"]);` | Immutable array. Cannot change values. |
| **`dict`** | `Object` / `Map` | `d = {"price": 27}` | `const d = { price: 27 };` | Access: Python `d["price"]` (no `d.price` for dicts). |
| **`NamedTuple`** | `readonly Interface` | `class Qty(NamedTuple): amount: float` | `interface Qty { readonly amount: number; }` | Immutable object with dot notation (`qty.amount`). |
| **Pydantic** | **Zod** + TypeScript | `class User(BaseModel): ...` | `const User = z.object({ ... });` | Runtime schema validation and sanitization. |

---

## 2. Common Syntax Comparisons

### A. Negative Indexing (Grabbing the Last Item)
* **Python:** `parts[-1]`
* **JavaScript:** `parts.at(-1)` or `parts[parts.length - 1]`
* Example: `["A", "B", "C"][-1]` gives `"C"`.

### B. String Contains (`in`)
* **Python:** `if "or" in inner:`
* **JavaScript:** `if (inner.includes("or"))`

### C. Spread / Unpack Operator (`*` and `**`)
* **List Unpack:**
  * Python: `asyncio.gather(*tasks)`
  * JavaScript: `Promise.all([...tasks])`
* **Dict / Object Unpack:**
  * Python: `RawProduct(**item_dict)`
  * JavaScript: `{ ...itemObject }`

---

## 3. Functions vs. Class Methods

| Type | Python Syntax | JavaScript Equivalent | Notes |
| :--- | :--- | :--- | :--- |
| **Standalone Function** | `def calc(): ...` | `function calc() { ... }` | Outside any class. No `self`, no `this`. |
| **Instance Method** | `def run(self): ...` | `run() { this.name ... }` | Python requires **`self`** as 1st parameter; JS uses `this`. |
| **Class Method** | `@classmethod def make(cls): ...` | `static make() { ... }` (factory) | Works with the class blueprint before object is built. |
| **Static Method** | `@staticmethod def helper(): ...` | `static helper() { ... }` | Utility function inside class; needs neither `self` nor `cls`. |

---

## 4. `zip()` — Pairing Two Lists Together

Glues two lists into pairs side-by-side:

```python
# Python
names = ["Rahul", "Pooja"]
marks = [95, 88]

for name, mark in zip(names, marks):
    print(name, mark)
```

**JavaScript Equivalent:**
```javascript
// JS doesn't have a built-in zip, you'd have to write:
names.forEach((name, i) => {
    const mark = marks[i];
    console.log(name, mark);
});
```

* **In our project:** `for p, res in zip(target_platforms, results):` pairs `"blinkit"` with `blinkit_result`.

---

## 5. `isinstance()` — Type & Crash Guard

Asks Python: **"Is this variable of this type?"**

```python
# Python
if isinstance(res, BaseException):
    output[p] = PlatformSearchResult(error=str(res))
```

**JavaScript Equivalent:**
```javascript
// JS: instanceof
if (res instanceof Error) {
    output[p] = { error: res.message };
}
```

---

## 6. Async & Concurrency

| Action | Python (`asyncio` / `httpx`) | JavaScript (`fetch` / `Promise`) |
| :--- | :--- | :--- |
| **Async function** | `async def search():` | `async function search() {` |
| **Wait for promise** | `await client.get(url)` | `await fetch(url)` |
| **Run in parallel** | `await asyncio.gather(*tasks)` | `await Promise.all(tasks)` |
| **Handle all settled** | `asyncio.gather(*tasks, return_exceptions=True)` | `Promise.allSettled(tasks)` |

---

## 7. Pydantic Validators (`mode="before"`)

Like a **Zod preprocess / transform** hook:

```python
# Python
@field_validator("id", mode="before")
@classmethod
def coerce_id(cls, v):
    return str(v) if v is not None else ""
```

**JavaScript (Zod) Equivalent:**
```typescript
// TypeScript Zod
const IdSchema = z.preprocess((val) => (val !== null ? String(val) : ""), z.string());
```
* **`mode="before"`**: Cleans dirty input *before* Pydantic enforces types, preventing server crashes.

---

## 8. File I/O Appending & In-Memory Deduplication (Audit Logging)

Used in `quantity_parser.py` to record unhandled quantities for future review:

```python
# Python
with open("data/unhandled_quantities.log", "a", encoding="utf-8") as f:
    f.write(f"[{timestamp}] {unhandled_str}\n")
```

**JavaScript Equivalent:**
```javascript
// JS: fs.appendFileSync
import fs from "fs";
fs.appendFileSync("data/unhandled_quantities.log", `[${timestamp}] ${unhandledStr}\n`);
```

* **`"a"` Mode:** Appends to the end of the file without overwriting existing lines.
* **`with open(...) as f:`**: The Context Manager. Automatically closes the file even if an error occurs (like a `try...finally { f.close() }` block in JS).

