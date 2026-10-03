# SahiBhav AI - Frontend Web Application (`sahibhav-web`)

Modern, high-performance React + TypeScript single-page application built with Vite and Vanilla CSS. Designed to deliver real-time grocery price optimization across India's leading quick-commerce platforms (**Blinkit**, **Zepto**, **Swiggy Instamart**, and **BigBasket BBNow**).

---

## 🎨 Design & Aesthetic Features

- **Dark Glassmorphism Architecture**:
  - Deep blue/space dark backgrounds (`#080B11`, `#0F1420`) with subtle multi-platform ambient radial gradients.
  - Backdrop blur effects (`backdrop-filter: blur(20px)`), glowing accents, and smooth border transitions.
- **Brand Palette & Indicator Pills**:
  - 🟡 **Blinkit**: `#F8CB46`
  - 🟣 **Zepto**: `#8B30EC`
  - 🟠 **Swiggy Instamart**: `#FC8019`
  - 🟢 **BigBasket BBNow**: `#84C225`
- **Micro-Animations & Keyframes**:
  - Real-time 4-step pipeline progress card during live searches (`Groq NLU` ➔ `4-App Scraper` ➔ `Combo Optimizer` ➔ `AI Recommendation`).
  - Confetti celebration fireworks powered by `canvas-confetti` whenever the user saves money.
  - Fluid hover states, micro-bounces, and card elevations.

---

## ⚡ Interactive Capabilities

1. **Multilingual Omnibar & Quick Prompt Pills**:
   - Supports natural grocery queries in any language/dialect (**Odia**, **Hindi**, **Hinglish**, **English**, **Bengali**, etc.).
   - Interactive prompt chips prefill queries instantly.
2. **Delivery Location Selector**:
   - Preset delivery coordinates with live GPS pin (Bhubaneswar, Bengaluru, New Delhi, Mumbai).
3. **Conversational AI Speech Bubble**:
   - Displays Groq LLM natural language recommendation with detected language badge.
4. **Hero Winner Recommendation Card**:
   - Displays the recommended basket (single platform or split-cart combination).
   - Clear breakdown of items, subtotal, delivery fee rule (e.g. ₹30 if < ₹200, FREE if ≥ ₹200), and total checkout price.
   - Platform deeplink buttons to open the respective app directly for instant checkout.
5. **Multi-Tab Store Comparisons**:
   - **Winner Recommendation**: Full detailed basket with delivery fee math.
   - **Compare Single Stores**: Side-by-side view of Blinkit, Zepto, Swiggy, and BigBasket carts.
   - **Split Combos**: Inspection of 2-store combinations to verify whether splitting is cost-effective.

---

## 🚀 Running the App

### 1. Start Backend (FastAPI)
```powershell
cd server
.venv\Scripts\python -m uvicorn api.main:app --port 8000 --reload
```
API runs on: `http://localhost:8000` (Swagger docs: `http://localhost:8000/docs`)

### 2. Start Frontend (Vite)
```powershell
cd sahibhav-web
npm run dev
```
Web app runs on: `http://localhost:5173`
