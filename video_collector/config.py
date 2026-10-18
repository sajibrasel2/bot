import os
from dotenv import load_dotenv

load_dotenv()

def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if not val or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default

# ── Video Collector Bot Config ───────────────────
# You can set this in .env or update it via Web Admin Panel
VC_BOT_TOKEN: str = os.getenv("VC_BOT_TOKEN", "8949426682:AAEPX3e3kOrVYFGqTfE3PiiW3CYnSGjY8jc")
VC_BOT_USERNAME: str = os.getenv("VC_BOT_USERNAME", "newideos_bot")
VC_OWNER_ID: int = _get_int("OWNER_ID", 8904339611)

# ── MySQL Config (Uses same DB) ──────────────────
MYSQL_HOST: str     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int     = _get_int("MYSQL_PORT", 3306)
MYSQL_USER: str     = os.getenv("MYSQL_USER", "techandc_bot")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "12345Sajibs6@")
MYSQL_DB: str       = os.getenv("MYSQL_DB", "techandc_tlbot")

# Optional delay (seconds) between forwarding videos
FORWARD_DELAY_SECONDS: float = float(os.getenv("VC_FORWARD_DELAY", "1.5"))
