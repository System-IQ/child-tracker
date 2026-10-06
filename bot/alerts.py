"""مراقب خلفية: يفحص البطارية، السرعة، السياج الجغرافي، و SOS"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode
import db
from gpx_export import haversine_m

log = logging.getLogger(__name__)

# تجنّب التكرار: نتذكر آخر تنبيه لكل (device_id, type)
_last_alert: dict[str, datetime] = {}
COOLDOWN_MIN = 15
BATTERY_LOW = 15
SPEED_HIGH_KMH = 60


def _can_alert(key: str) -> bool:
    now = datetime.now(timezone.utc)
    last = _last_alert.get(key)
    if last and (now - last) < timedelta(minutes=COOLDOWN_MIN):
        return False
    _last_alert[key] = now
    return True


async def _send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.warning(f"فشل الإرسال: {e}")


async def check_all(bot: Bot, chat_id: int):
    try:
        devices = db.list_devices()
    except Exception as e:
        log.warning(f"تعذّر جلب الأجهزة: {e}")
        return

    for dev in devices:
        did = dev["id"]
        name = dev.get("name", did)
        try:
            last = db.get_latest(did)
        except Exception:
            continue
        if not last:
            continue

        # 🔋 البطارية
        bat = last.get("battery")
        if bat is not None and bat < BATTERY_LOW and _can_alert(f"{did}:battery"):
            await _send(bot, chat_id, f"🔋 *بطارية {name} منخفضة:* `{bat}%`")

        # 🚗 السرعة العالية
        spd = (last.get("speed") or 0) * 3.6
        if spd > SPEED_HIGH_KMH and _can_alert(f"{did}:speed"):
            await _send(bot, chat_id, f"🚗 *{name} في مركبة؟* السرعة: `{spd:.0f} km/h`")

        # 🚧 السياج الجغرافي
        try:
            fences = db.get_geofences(did)
        except Exception:
            fences = []
        for f in fences:
            d = haversine_m(last["latitude"], last["longitude"],
                            f["latitude"], f["longitude"])
            inside = d <= f["radius_m"]
            key = f"{did}:fence:{f['id']}:{'in' if inside else 'out'}"
            if not inside and _can_alert(key):
                await _send(bot, chat_id,
                    f"🚧 *{name} خرج من* `{f['name']}`\n"
                    f"المسافة: `{d:.0f} m` عن المركز")

        # 🆘 SOS جديد
        try:
            sos = db.get_sos_events(did, hours=1)
        except Exception:
            sos = []
        for s in sos:
            key = f"{did}:sos:{s['id']}"
            if _can_alert(key):
                await _send(bot, chat_id,
                    f"🆘🆘 *استغاثة من {name}!*\n"
                    f"📍 {s['latitude']}, {s['longitude']}\n"
                    f"🕐 {s.get('timestamp','')}\n"
                    f"[فتح الخريطة](https://www.google.com/maps?q={s['latitude']},{s['longitude']})")


async def monitor_loop(bot: Bot, chat_id: int, interval_s: int = 60):
    while True:
        try:
            await check_all(bot, chat_id)
        except Exception as e:
            log.exception(f"خطأ في المراقب: {e}")
        await asyncio.sleep(interval_s)
