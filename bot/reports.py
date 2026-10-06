"""تقارير تلقائية يومية وأسبوعية"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import pytz
from telegram import Bot
from telegram.constants import ParseMode
import db
from gpx_export import compute_stats

log = logging.getLogger(__name__)


def _tashkent_now(tz_name: str) -> datetime:
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.UTC
    return datetime.now(tz)


async def daily_report(bot: Bot, chat_id: int, tz_name: str = "Asia/Baghdad"):
    devices = db.list_devices()
    if not devices:
        return
    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    lines = [f"📊 *التقرير اليومي* — {_tashkent_now(tz_name).strftime('%Y-%m-%d')}\n"]

    for d in devices:
        did, name = d["id"], d.get("name", d["id"])
        pts = db.get_track(did, hours=24)
        if not pts:
            lines.append(f"👶 *{name}*: لا بيانات")
            continue
        s = compute_stats(pts)
        last = pts[-1]
        lines.append(
            f"👶 *{name}*\n"
            f"  • المسافة: `{s['distance_km']} km`\n"
            f"  • زمن الحركة: `{s['moving_time_min']} د`\n"
            f"  • أقصى سرعة: `{s['max_speed_kmh']} km/h`\n"
            f"  • آخر موقع: `{last['latitude']:.4f}, {last['longitude']:.4f}`\n"
            f"  • [📍 فتح](https://www.google.com/maps?q={last['latitude']},{last['longitude']})\n"
        )
    await bot.send_message(chat_id, "\n".join(lines),
                           parse_mode=ParseMode.MARKDOWN,
                           disable_web_page_preview=True)


async def weekly_report(bot: Bot, chat_id: int, tz_name: str = "Asia/Baghdad"):
    devices = db.list_devices()
    if not devices:
        return
    lines = [f"📈 *التقرير الأسبوعي* — {_tashkent_now(tz_name).strftime('%Y-%W')}\n"]
    for d in devices:
        did, name = d["id"], d.get("name", d["id"])
        pts = db.get_track(did, hours=24 * 7)
        if not pts:
            continue
        s = compute_stats(pts)
        lines.append(
            f"👶 *{name}*\n"
            f"  • إجمالي المسافة: `{s['distance_km']} km`\n"
            f"  • ساعات الحركة: `{round(s['moving_time_min']/60, 1)} h`\n"
            f"  • عدد النقاط: `{s['points']}`\n"
        )
    await bot.send_message(chat_id, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def report_scheduler(bot: Bot, chat_id: int, hour_utc: int, tz_name: str):
    """يشغّل التقرير اليومي يوميًا في الساعة المحددة بتوقيت بغداد"""
    last_run_day = None
    while True:
        now_local = _tashkent_now(tz_name)
        if now_local.hour == hour_utc and last_run_day != now_local.date():
            try:
                await daily_report(bot, chat_id, tz_name)
                # كل يوم أحد: أرسل التقرير الأسبوعي أيضاً
                if now_local.weekday() == 6:
                    await weekly_report(bot, chat_id, tz_name)
                last_run_day = now_local.date()
            except Exception as e:
                log.exception(f"فشل التقرير: {e}")
        await asyncio.sleep(60 * 5)
