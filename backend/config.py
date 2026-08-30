from pydantic_settings import BaseSettings
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# All path resolution is relative to this file's location.
# This means the project works regardless of where you run it from.
# ---------------------------------------------------------------------------

BASE_DIR       = Path(__file__).resolve().parent.parent   # project root
MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data" / "emails.json"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
# pydantic_settings reads values from:
#   1. Environment variables (os.environ)
#   2. The .env file at project root
#   3. The defaults defined below
#
# Priority: env vars > .env file > defaults
#
# This means in production you set real env vars and never touch .env.
# In development you just edit .env.
# ---------------------------------------------------------------------------

class Settings(BaseSettings):

    # --- App ---
    APP_NAME:    str = "AI Email Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG:       bool = True

    # --- Ollama ---
    # Ollama runs locally as a service on port 11434 by default.
    # OLLAMA_MODEL is the model tag — must match what you pulled via
    # `ollama pull mistral:7b-instruct`
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL:    str = "mistral:7b-instruct"

    # --- Gmail API ---
    # These are populated from .env after OAuth setup.
    # Left empty for now — used in the Gmail wiring step at end of V1.
    GMAIL_CREDENTIALS_PATH: str = str(BASE_DIR / "credentials.json")
    GMAIL_TOKEN_PATH:        str = str(BASE_DIR / "token.json")
    GMAIL_SCOPES:            list[str] = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send"
    ]

     # --- Gmail toggle ---
    # V1 defaults to mock data for safety — flipping this requires a
    # real credentials.json and completed OAuth flow (see gmail_client.py).
    USE_GMAIL:      bool = False
    GMAIL_MAX_RESULTS: int = 10

    # --- Confidence Thresholds ---
    # V1: rule-based classifier uses these to decide confidence level.
    # V3: confidence engine will refine these dynamically.
    HIGH_CONFIDENCE_THRESHOLD: float = 0.85
    LOW_CONFIDENCE_THRESHOLD:  float = 0.50

    # --- Generation ---
    # Controls how the model generates replies.
    # temperature=0.3 keeps replies professional and consistent.
    # Higher values (0.7+) produce more varied but less predictable output.
    MAX_TOKENS:  int   = 512
    TEMPERATURE: float = 0.3

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------
# Every module imports this one object:
#
#   from backend.config import settings
#   print(settings.OLLAMA_MODEL)
#
# ---------------------------------------------------------------------------

settings = Settings()