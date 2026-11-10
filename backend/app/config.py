"""Settings read from environment variables (see backend/.env.example)."""
import os
from zoneinfo import ZoneInfo

try:  # load backend/.env when running locally
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:  # pragma: no cover
    pass


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:  # unset or blank (e.g. "MOCK_LLM=" in .env) -> use the default
        return default
    return value in {"1", "true", "yes", "on"}


def _str(name: str, default: str = "") -> str:
    """Like os.getenv, but a blank value in .env also falls back to the default."""
    return os.getenv(name, "").strip() or default


GEMINI_API_KEY = _str("GEMINI_API_KEY") or _str("GOOGLE_API_KEY")
GEMINI_MODEL = _str("GEMINI_MODEL", "gemini-2.5-flash")
if GEMINI_API_KEY:
    # ADK and google-genai read GOOGLE_API_KEY; use the AI Studio key, not Vertex AI
    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

# "adk" runs every agent through Google's Agent Development Kit.
# "genai" calls the Gemini API directly (fallback if ADK misbehaves).
AGENT_RUNTIME = _str("AGENT_RUNTIME", "adk").lower()

# Mock mode = no Gemini calls; deterministic, template-written agent output.
# On automatically when there is no API key, so the demo always runs.
MOCK_LLM = _bool("MOCK_LLM", default=not GEMINI_API_KEY)

# "local" = JSON file store (dev, tests). "firestore" = Google Cloud Firestore.
STORE = _str("STORE", "local").lower()
DATA_DIR = _str("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

GITHUB_TOKEN = _str("GITHUB_TOKEN")
TAPIN_DEVICE_TOKEN = _str("TAPIN_DEVICE_TOKEN")

CORS_ORIGINS = [o.strip() for o in _str("CORS_ORIGINS", "*").split(",") if o.strip()]

TZ = ZoneInfo(_str("TEAM_TIMEZONE", "Asia/Kuala_Lumpur"))
