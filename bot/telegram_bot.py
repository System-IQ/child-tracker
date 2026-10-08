#!/usr/bin/env python3
"""Child Tracker Bot v3.0 - محسّن بالكامل"""
import os, asyncio, logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           ContextTypes)

import db
import alerts
import reports
from config import get_config
from gpx_export import compute_stats, to_gpx_bytes, to_kml_bytes, to_csv_bytes
from map_generator import build_map_html
from heatmap_generator import build_heatmap_html
from track_simplify import clean_track
import analytics

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DEFAULT_DEVICE = os.getenv("DEVICE_ID", "child_phone_01")

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

_selected: dict[int, str] = {}

def is_owner(update: Update) -> bool:
    if not CHAT_ID: return True
    uid = str(update.effective_user.id)
    if uid != str(CHAT_ID):
        log.warning(f"🚫 وصول مرفوض: {uid}")
        return False
    return True

def current_device(chat_id: int) -> str:
    return _selected.get(chat_id, DEFAULT_DEVICE)

def fmt_age(ts_str: str) -> str:
    """يحول timestamp إلى عمر مقروء بالعربية"""
    if not ts_str: return "غير معروف"
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - ts).total_seconds())
        if secs < 0: return "الآن"
        if secs < 60: return f"قبل {secs} ثانية"
        if secs < 3600: return f"قبل {secs//60} دقيقة"
        if secs < 86400: return f"قبل {secs//3600} ساعة"
        return f"قبل {secs//86400} يوم"
    except Exception:
        return ts_str[:19]

def is_stale(ts_str: str, minutes: int = 10) -> bool:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() > minutes * 60
    except Exception:
        return True


# ============ أوامر ============
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    devices = db.list_devices()
    if not devices:
        await update.message.reply_text("⚠️ لا توجد أجهزة.")
        return
    rows = [[InlineKeyboardButton(f"👶 {d.get('name', d['id'])}", callback_data=f"dev:{d['id']}")]
            for d in devices]
    rows.append([InlineKeyboardButton("🔄 تحديث", callback_data="refresh")])
    await update.message.reply_text(
        "🛡️ *Child Tracker v3.0*\nاختر الطفل:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    dev = current_device(update.effective_chat.id)
    kb = [
        [InlineKeyboardButton("📍 الموقع الحالي", callback_data="current"),
         InlineKeyboardButton("🔄 طلب موقع فوري", callback_data="force_locate")],
        [InlineKeyboardButton("📂 طلب جميع المسارات", callback_data="track_all")],
        [InlineKeyboardButton("🗺️ خريطة تفاعلية", callback_data="map"),
         InlineKeyboardButton("🔥 خريطة حرارية", callback_data="heat")],
        [InlineKeyboardButton("🛑 أماكن التوقف", callback_data="stops"),
         InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🏠 اكتشاف الأماكن", callback_data="places"),
         InlineKeyboardButton("📅 ملخص اليوم", callback_data="daily")],
        [InlineKeyboardButton("🚧 السياج الجغرافي", callback_data="fences"),
         InlineKeyboardButton("🆘 سجل SOS", callback_data="sos")],
        [InlineKeyboardButton("📡 أوامر عن بعد", callback_data="cmds"),
         InlineKeyboardButton("🔀 تبديل الطفل", callback_data="refresh")],
    ]
    await update.message.reply_text(
        f"🛡️ *لوحة تحكم {dev}*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_live(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    await send_current(update.effective_chat.id, ctx)


# ============ الإرسال ============
async def send_current(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    p = db.get_latest(dev)
    if not p:
        await ctx.bot.send_message(chat_id, "⚠️ لا توجد بيانات موقع بعد.")
        return
    spd = (p.get("speed") or 0) * 3.6
    acc = p.get("accuracy") or 0
    bat = p.get("battery")
    ts = p.get("timestamp", "")
    age = fmt_age(ts)
    stale = is_stale(ts, minutes=10)
    header = "🟢 *موقع حديث*" if not stale else "🟡 *موقع قديم*"
    text = (
        f"{header} — {dev}\n"
        f"• الإحداثيات: `{p['latitude']:.6f}, {p['longitude']:.6f}`\n"
        f"• الدقة: `±{acc:.1f} m`\n"
        f"• السرعة: `{spd:.1f} km/h`\n"
        + (f"• البطارية: `{bat}%`\n" if bat is not None else "")
        + f"• آخر تحديث: *{age}*\n"
        + (f"• الوقت: `{ts[:19]}`\n" if stale else "")
        + f"\n[🌍 Google Maps](https://www.google.com/maps?q={p['latitude']},{p['longitude']})"
    )
    if stale:
        text += "\n\n💡 *للحصول على موقع محدّث، اضغط:* `/locate`"
    await ctx.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN,
                               disable_web_page_preview=True)


async def cmd_force_locate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    dev = current_device(update.effective_chat.id)
    db.queue_command(dev, "locate", {"requested_by": update.effective_user.id})
    await update.message.reply_text(
        "📡 *تم إرسال طلب تحديد موقع فوري.*\n\n"
        "سيستجيب التطبيق خلال ثوانٍ عند اتصال الجهاز بالإنترنت.\n"
        "استخدم `/live` بعد 10-30 ثانية لرؤية الموقع المحدّث.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def send_track_all(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    """يرسل مسارات 1س + 6س + 24س دفعة واحدة"""
    dev = current_device(chat_id)
    ranges = [(1, "ساعة"), (6, "6 ساعات"), (24, "24 ساعة")]
    found_any = False
    await ctx.bot.send_message(chat_id, f"📂 *جاري إعداد المسارات لـ {dev}*...",
                                parse_mode=ParseMode.MARKDOWN)
    ts = int(datetime.now(timezone.utc).timestamp())
    for hours, label in ranges:
        pts = db.get_track(dev, hours=hours)
        if not pts:
            await ctx.bot.send_message(chat_id, f"⚠️ لا بيانات لآخر {label}.")
            continue
        found_any = True
        clean = clean_track(pts)
        stats = compute_stats(clean)
        cap = (f"📍 *{dev}* — آخر {label}\n"
               f"• النقاط: `{stats['points']}`\n"
               f"• المسافة: `{stats['distance_km']} km`\n"
               f"• متوسط: `{stats['avg_speed_kmh']} km/h`\n"
               f"• أقصى: `{stats['max_speed_kmh']} km/h`")
        # GPX
        await ctx.bot.send_document(
            chat_id, document=to_gpx_bytes(clean, dev),
            filename=f"track_{hours}h_{ts}.gpx",
            caption=cap, parse_mode=ParseMode.MARKDOWN,
        )
        # KML + CSV مختصران
        await ctx.bot.send_document(
            chat_id, document=to_kml_bytes(clean, dev),
            filename=f"track_{hours}h_{ts}.kml",
        )
        await ctx.bot.send_document(
            chat_id, document=to_csv_bytes(clean),
            filename=f"track_{hours}h_{ts}.csv",
        )
    if not found_any:
        await ctx.bot.send_message(chat_id, "⚠️ لا توجد بيانات في أي مدى زمني.")


async def send_stops(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    """أماكن التوقف مع المدة الدقيقة"""
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    stops = analytics.find_stops(pts, min_duration_min=3, max_distance_m=80)
    if not stops:
        await ctx.bot.send_message(chat_id, "ℹ️ لا توجد توقفات ملحوظة (≥3 دقائق) خلال 24 ساعة.")
        return
    lines = [f"🛑 *أماكن التوقف — {dev}*\n_آخر 24 ساعة_\n"]
    for i, s in enumerate(stops[:15], 1):
        dur = int(s['duration_sec'])
        h, m = dur // 3600, (dur % 3600) // 60
        sec = dur % 60
        dur_str = f"{h}س {m}د {sec}ث" if h else (f"{m}د {sec}ث" if m else f"{sec}ث")
        lines.append(
            f"{i}. 📍 `{s['lat']:.5f}, {s['lon']:.5f}`\n"
            f"   • المدة: *{dur_str}*\n"
            f"   • من: `{s['start'][11:19]}` → إلى: `{s['end'][11:19]}`\n"
            f"   • [فتح](https://www.google.com/maps?q={s['lat']},{s['lon']})"
        )
    await ctx.bot.send_message(chat_id, "\n".join(lines),
                               parse_mode=ParseMode.MARKDOWN,
                               disable_web_page_preview=True)


async def send_map(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    # جرب 6 ساعات، ثم 24، ثم 7 أيام
    for hours in (6, 24, 168):
        pts = db.get_track(dev, hours=hours)
        if pts and len(pts) >= 2:
            stats = compute_stats(clean_track(pts))
            html = build_map_html(pts, dev, stats)
            ts = int(datetime.now(timezone.utc).timestamp())
            await ctx.bot.send_document(
                chat_id, document=html,
                filename=f"map_{dev}_{ts}.html",
                caption=f"🗺️ خريطة — آخر {hours} ساعة\nافتح في المتصفح.",
            )
            return
    await ctx.bot.send_message(chat_id, "⚠️ لا توجد نقاط كافية لرسم خريطة.")


async def send_heatmap(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    for hours in (24, 168, 720):
        pts = db.get_track(dev, hours=hours)
        if pts and len(pts) >= 5:
            html = build_heatmap_html(pts, dev)
            ts = int(datetime.now(timezone.utc).timestamp())
            await ctx.bot.send_document(
                chat_id, document=html,
                filename=f"heatmap_{dev}_{ts}.html",
                caption=f"🔥 خريطة حرارية — آخر {hours} ساعة\n_تعمل أوفلاين_",
            )
            return
    await ctx.bot.send_message(chat_id, "⚠️ لا توجد نقاط كافية.")


async def send_stats(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات خلال 24 ساعة.")
        return
    s = compute_stats(pts)
    stops = analytics.find_stops(pts, min_duration_min=3, max_distance_m=80)
    txt = (f"📊 *إحصائيات {dev} — 24 ساعة*\n"
           f"• النقاط: `{s['points']}`\n"
           f"• المسافة: `{s['distance_km']} km`\n"
           f"• زمن الحركة: `{s['moving_time_min']} د`\n"
           f"• متوسط: `{s['avg_speed_kmh']} km/h`\n"
           f"• أقصى: `{s['max_speed_kmh']} km/h`\n"
           f"• عدد التوقفات: `{len(stops)}`")
    await ctx.bot.send_message(chat_id, txt, parse_mode=ParseMode.MARKDOWN)


async def send_places(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24*7)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    places = analytics.detect_home_school(pts)
    lines = [f"🏠 *اكتشاف الأماكن — {dev}*\n"]
    if places.get("home"):
        h = places["home"]
        lines.append(f"🏠 *البيت المحتمل*\n  • `{h['lat']:.5f}, {h['lon']:.5f}`\n  • زيارات: {h['visits']}\n  • المدة: {h['total_minutes']} د")
    if places.get("school"):
        s = places["school"]
        lines.append(f"🏫 *المدرسة المحتملة*\n  • `{s['lat']:.5f}, {s['lon']:.5f}`\n  • زيارات: {s['visits']}\n  • المدة: {s['total_minutes']} د")
    if len(lines) == 1:
        lines.append("لم تُكتشف أماكن متكررة.")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def send_daily(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    s = analytics.daily_summary(pts)
    txt = (f"📅 *ملخص اليوم — {dev}*\n"
           f"• النقاط: `{len(pts)}`\n"
           f"• ساعات النشاط: `{s.get('active_hours', [])}`\n"
           f"• التوقفات: `{s.get('n_stops', 0)}`")
    await ctx.bot.send_message(chat_id, txt, parse_mode=ParseMode.MARKDOWN)


async def send_fences(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    fences = db.get_geofences(dev)
    if not fences:
        await ctx.bot.send_message(chat_id, "🚧 لا أسوار. أضف:\n`/fence اسم خط_العرض خط_الطول نصف_القطر`",
                                    parse_mode=ParseMode.MARKDOWN)
        return
    txt = f"🚧 *أسوار {dev}:*\n" + "\n".join(
        f"• `{f['name']}` — {f['radius_m']}m" for f in fences)
    await ctx.bot.send_message(chat_id, txt, parse_mode=ParseMode.MARKDOWN)


async def send_sos(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    events = db.get_sos_events(dev, hours=48)
    if not events:
        await ctx.bot.send_message(chat_id, "🆘 لا استغاثات.")
        return
    for e in events[:5]:
        await ctx.bot.send_message(chat_id,
            f"🆘 *{e.get('device_id')}*\n{e.get('timestamp','')[:19]}\n"
            f"[📍 فتح](https://www.google.com/maps?q={e['latitude']},{e['longitude']})",
            parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ============ الأوامر النصية ============
async def cmd_locate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_force_locate(update, ctx)

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    await reports.daily_report(ctx.bot, update.effective_chat.id)

async def cmd_fence(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    args = ctx.args
    if len(args) < 4:
        await update.message.reply_text(
            "الاستخدام: `/fence اسم LAT LON RADIUS`\n"
            "مثال: `/fence البيت 36.1550 44.0743 200`",
            parse_mode=ParseMode.MARKDOWN)
        return
    name, lat, lon, r = args[0], float(args[1]), float(args[2]), float(args[3])
    dev = current_device(update.effective_chat.id)
    f = db.add_geofence(dev, name, lat, lon, r)
    await update.message.reply_text(f"✅ سور `{f['name']}` ({r}m)", parse_mode=ParseMode.MARKDOWN)

async def cmd_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "الأوامر:\n`/cmd locate` - موقع فوري\n"
            "`/cmd restart` - إعادة تشغيل\n"
            "`/cmd sync` - مزامنة كامل",
            parse_mode=ParseMode.MARKDOWN)
        return
    dev = current_device(update.effective_chat.id)
    db.queue_command(dev, args[0], {"by": update.effective_user.id})
    await update.message.reply_text(f"📡 أمر `{args[0]}` في الطابور.", parse_mode=ParseMode.MARKDOWN)


# ============ الأزرار ============
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_owner(update): return
    data = q.data
    chat = q.message.chat_id

    if data == "refresh":
        await q.message.reply_text("أرسل /start للاختيار.")
    elif data.startswith("dev:"):
        _selected[chat] = data.split(":", 1)[1]
        await q.message.reply_text(f"✅ اختير: `{_selected[chat]}`. أرسل /menu.",
                                    parse_mode=ParseMode.MARKDOWN)
    elif data == "current": await send_current(chat, ctx)
    elif data == "force_locate": await cmd_force_locate(update, ctx)
    elif data == "track_all": await send_track_all(chat, ctx)
    elif data == "map": await send_map(chat, ctx)
    elif data == "heat": await send_heatmap(chat, ctx)
    elif data == "stops": await send_stops(chat, ctx)
    elif data == "stats": await send_stats(chat, ctx)
    elif data == "places": await send_places(chat, ctx)
    elif data == "daily": await send_daily(chat, ctx)
    elif data == "fences": await send_fences(chat, ctx)
    elif data == "sos": await send_sos(chat, ctx)
    elif data == "cmds":
        await q.message.reply_text("📡 `/cmd locate` / `/cmd restart` / `/cmd sync`",
                                    parse_mode=ParseMode.MARKDOWN)


# ============ التشغيل ============
async def post_init(app: Application):
    cfg = get_config()
    asyncio.create_task(alerts.monitor_loop(app.bot, cfg.chat_id, interval_s=60))
    asyncio.create_task(reports.report_scheduler(app.bot, cfg.chat_id, cfg.report_hour, cfg.timezone))
    log.info("🚀 المراقب الخلفي يعمل")

def main():
    if not all([BOT_TOKEN, CHAT_ID]):
        raise SystemExit("❌ BOT_TOKEN و CHAT_ID مطلوبان")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("live", cmd_live))
    app.add_handler(CommandHandler("locate", cmd_locate))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("fence", cmd_fence))
    app.add_handler(CommandHandler("cmd", cmd_command))
    app.add_handler(CallbackQueryHandler(on_button))
    log.info("✅ Child Tracker v3.0 يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
