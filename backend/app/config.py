"""Settings read from environment variables (see backend/.env.example)."""
import os
from zoneinfo import ZoneInfo

try:  # load backend/.env when running locally
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:  # pragma: no cover
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
if GEMINI_API_KEY:
    # ADK and google-genai read GOOGLE_API_KEY; use the AI Studio key, not Vertex AI
    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

# "adk" runs every agent through Google's Agent Development Kit.
# "genai" calls the Gemini API directly (fallback if ADK misbehaves).
AGENT_RUNTIME = os.getenv("AGENT_RUNTIME", "adk").lower()

# Mock mode = no Gemini calls; deterministic, template-written agent output.
# On automatically when there is no API key, so the demo always runs.
MOCK_LLM = _bool("MOCK_LLM", default=not GEMINI_API_KEY)

# "local" = JSON file store (dev, tests). "firestore" = Google Cloud Firestore.
STORE = os.getenv("STORE", "local").lower()
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
TAPIN_DEVICE_TOKEN = os.getenv("TAPIN_DEVICE_TOKEN", "")

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

TZ = ZoneInfo(os.getenv("TEAM_TIMEZONE", "Asia/Kuala_Lumpur"))
