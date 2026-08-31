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

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8670819072:AAGz39QtNS7TGwOmVEm4GM2wUsaUvcYmcuU")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "sweetnikitabot")
OWNER_ID: int = _get_int("OWNER_ID", 8904339611)
LOG_CHANNEL_ID: int = _get_int("LOG_CHANNEL_ID", 0)
WEB_APP_URL: str = os.getenv("WEB_APP_URL", "https://techandclick.site/bot/")

# ── MySQL config ──────────────────────────────────
MYSQL_HOST: str     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int     = _get_int("MYSQL_PORT", 3306)
MYSQL_USER: str     = os.getenv("MYSQL_USER", "techandc_bot")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "12345Sajibs6@")
MYSQL_DB: str       = os.getenv("MYSQL_DB", "techandc_tlbot")

# Spam protection defaults
MAX_FLOOD_MESSAGES: int = 7        # messages per window
FLOOD_WINDOW_SECONDS: int = 5      # time window in seconds
MAX_WARNS: int = 3                 # warns before auto-ban

# Mute duration defaults (seconds)
DEFAULT_MUTE_TIME: int = 3600      # 1 hour

WARN_EXPIRY_DAYS: int = 30         # warns expire after N days (0 = never)
