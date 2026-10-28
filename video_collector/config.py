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

# ── Telegram MTProto (Userbot) Config ─────────────
TG_API_ID: int = _get_int("TG_API_ID", 37114956)
TG_API_HASH: str = os.getenv("TG_API_HASH", "a0f545049ee3c05ccaedea2566fd18e1")
SESSION_NAME: str = os.getenv("VC_SESSION_NAME", "collector_userbot")

# ── Video Collector Bot Config ───────────────────
# You can set this in .env or update it via Web Admin Panel
VC_BOT_TOKEN: str = os.getenv("VC_BOT_TOKEN", "8335808536:AAE-zP-qFTVhwx4uBiii_LrHAbXokWo_bXY")
VC_BOT_USERNAME: str = os.getenv("VC_BOT_USERNAME", "videocoolect_bot")
VC_OWNER_ID: int = _get_int("OWNER_ID", 8904339611)

# ── MySQL Config (Uses same DB) ──────────────────
MYSQL_HOST: str     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int     = _get_int("MYSQL_PORT", 3306)
MYSQL_USER: str     = os.getenv("MYSQL_USER", "techandc_bot")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "12345Sajibs6@")
MYSQL_DB: str       = os.getenv("MYSQL_DB", "techandc_tlbot")

# Optional delay (seconds) between forwarding videos
FORWARD_DELAY_SECONDS: float = float(os.getenv("VC_FORWARD_DELAY", "1.5"))
