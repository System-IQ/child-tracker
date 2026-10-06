"""إعدادات مركزية مع تحقق من الصحة"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _req(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"❌ متغير البيئة {key} مطلوب")
    return v


@dataclass(frozen=True)
class Config:
    bot_token: str
    chat_id: int
    supabase_url: str
    supabase_key: str
    default_device: str
    fetch_interval: int
    battery_low: int = 15
    speed_high_kmh: int = 60
    alert_cooldown_min: int = 15
    report_hour: int = 20  # الساعة اليومية للتقرير (UTC)
    timezone: str = "Asia/Baghdad"

    @classmethod
    def load(cls) -> "Config":
        return cls(
            bot_token=_req("BOT_TOKEN"),
            chat_id=int(_req("CHAT_ID")),
            supabase_url=_req("SUPABASE_URL"),
            supabase_key=_req("SUPABASE_KEY"),
            default_device=os.getenv("DEVICE_ID", "child_phone_01"),
            fetch_interval=int(os.getenv("FETCH_INTERVAL", "300")),
            battery_low=int(os.getenv("BATTERY_LOW", "15")),
            speed_high_kmh=int(os.getenv("SPEED_HIGH_KMH", "60")),
            alert_cooldown_min=int(os.getenv("ALERT_COOLDOWN_MIN", "15")),
            report_hour=int(os.getenv("REPORT_HOUR", "20")),
            timezone=os.getenv("TIMEZONE", "Asia/Baghdad"),
        )


CFG: Config | None = None


def get_config() -> Config:
    global CFG
    if CFG is None:
        CFG = Config.load()
    return CFG
