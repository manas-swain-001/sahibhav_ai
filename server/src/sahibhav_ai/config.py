import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load .env from the server root
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "llama-3.1-8b-instant")
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "20.31"))
DEFAULT_LON = float(os.getenv("DEFAULT_LON", "85.88"))

qc_keys_raw = os.getenv("QUICK_COMMERCE_API_KEYS", "")
QUICKCOMMERCE_API_KEYS = [k.strip() for k in qc_keys_raw.split(",") if k.strip()]
QUICKCOMMERCE_API_KEY = (
    QUICKCOMMERCE_API_KEYS[0]
    if QUICKCOMMERCE_API_KEYS
    else (os.getenv("QUICK_COMMERCE_API_KEY") or os.getenv("QUICKCOMMERCE_API_KEY", ""))
)
QC_BASE_URL = os.getenv("QC_BASE_URL", "https://api.quickcommerceapi.com/v1/search")

SUPPORTED_PLATFORMS = ["BlinkIt", "Zepto", "Swiggy", "BigBasket"]

if not GROQ_API_KEY:
    raise ValueError(f"GROQ_API_KEY not found in environment or at {ENV_PATH}")

