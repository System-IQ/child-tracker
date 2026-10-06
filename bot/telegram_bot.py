#!/usr/bin/env python3
"""Child Tracker Bot v2.0 - نسخة مضاعفة القوة"""
import os, asyncio, logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           ContextTypes, MessageHandler, filters)

import db
import alerts
from gpx_export import compute_stats, to_gpx_bytes, to_kml_bytes, to_csv_bytes
from map_generator import build_map_html
from heatmap_generator import build_heatmap_html
from track_simplify import clean_track
import analytics
import reports
from config import get_config

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DEFAULT_DEVICE = os.getenv("DEVICE_ID", "child_phone_01")

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# معرف الجهاز الحالي لكل مستخدم (ذاكرة بسيطة)
_selected: dict[int, str] = {}


def is_owner(update: Update) -> bool:
    if not CHAT_ID:
        return True
    uid = str(update.effective_user.id)
    if uid != str(CHAT_ID):
        log.warning(f"🚫 وصول مرفوض: {uid}")
        return False
    return True


def current_device(chat_id: int) -> str:
    return _selected.get(chat_id, DEFAULT_DEVICE)


# ============ الأوامر الأساسية ============
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    devices = db.list_devices()
    if not devices:
        await update.message.reply_text(
            "⚠️ لا توجد أجهزة مسجّلة بعد. ثبّت التطبيق على جهاز طفلك أولاً."
        )
        return
    rows = [[InlineKeyboardButton(f"👶 {d.get('name', d['id'])}", callback_data=f"dev:{d['id']}")]
            for d in devices]
    rows.append([InlineKeyboardButton("🔄 تحديث", callback_data="refresh")])
    await update.message.reply_text(
        "🛡️ *Child Tracker v2.0*\nاختر الطفل:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    dev = current_device(update.effective_chat.id)
    kb = [
        [InlineKeyboardButton("📍 الموقع الحالي", callback_data="current"),
         InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
        [InlineKeyboardButton("📂 مسار 1 ساعة", callback_data="t:1"),
         InlineKeyboardButton("📂 مسار 6 ساعات", callback_data="t:6")],
        [InlineKeyboardButton("📂 مسار 24 ساعة", callback_data="t:24"),
         InlineKeyboardButton("🗺️ خريطة HTML", callback_data="map:6")],
        [InlineKeyboardButton("🔥 خريطة حرارية", callback_data="heat:24"),
         InlineKeyboardButton("🏠 الأماكن", callback_data="places")],
        [InlineKeyboardButton("📅 ملخص اليوم", callback_data="daily"),
         InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
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
    if not is_owner(update):
        return
    await send_current(update.effective_chat.id, ctx)


# ============ الإرسال ============
async def send_current(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    p = db.get_latest(dev)
    if not p:
        await ctx.bot.send_message(chat_id, "⚠️ لا توجد بيانات موقع.")
        return
    spd = (p.get("speed") or 0) * 3.6
    acc = p.get("accuracy") or 0
    bat = p.get("battery")
    text = (
        f"📍 *الموقع الحالي — {dev}*\n"
        f"• الإحداثيات: `{p['latitude']}, {p['longitude']}`\n"
        f"• الدقة: `±{acc:.1f} m`\n"
        f"• السرعة: `{spd:.1f} km/h`\n"
        + (f"• البطارية: `{bat}%`\n" if bat is not None else "")
        + f"• الوقت: `{p.get('timestamp','')}`\n\n"
        f"[🌍 Google Maps](https://www.google.com/maps?q={p['latitude']},{p['longitude']}) | "
        f"[📍 OSM](https://www.openstreetmap.org/?mlat={p['latitude']}&mlon={p['longitude']}#map=17/{p['latitude']}/{p['longitude']})"
    )
    await ctx.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN,
                               disable_web_page_preview=True)


async def send_track(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, hours: int):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=hours)
    if not pts:
        await ctx.bot.send_message(chat_id, f"⚠️ لا نقاط خلال {hours} ساعة.")
        return
    pts_clean = clean_track(pts)
    if len(pts_clean) < len(pts):
        log.info(f'تنقية: {len(pts)} → {len(pts_clean)} نقطة')
    stats = compute_stats(pts_clean)
    cap = (f"📍 *{dev}* — آخر {hours} ساعة\n"
           f"• النقاط: `{stats['points']}`\n"
           f"• المسافة: `{stats['distance_km']} km`\n"
           f"• متوسط: `{stats['avg_speed_kmh']} km/h`\n"
           f"• أقصى: `{stats['max_speed_kmh']} km/h`")
    ts = int(datetime.now(timezone.utc).timestamp())

    gpx = to_gpx_bytes(pts_clean, dev)
    await ctx.bot.send_document(chat_id, document=gpx,
                                filename=f"track_{hours}h_{ts}.gpx",
                                caption=cap, parse_mode=ParseMode.MARKDOWN)
    kml = to_kml_bytes(pts_clean, dev)
    await ctx.bot.send_document(chat_id, document=kml,
                                filename=f"track_{hours}h_{ts}.kml")
    csv = to_csv_bytes(pts_clean)
    await ctx.bot.send_document(chat_id, document=csv,
                                filename=f"track_{hours}h_{ts}.csv")


async def send_map(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, hours: int):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=hours)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    pts_clean = clean_track(pts)
    if len(pts_clean) < len(pts):
        log.info(f'تنقية: {len(pts)} → {len(pts_clean)} نقطة')
    stats = compute_stats(pts_clean)
    html = build_map_html(pts, dev, stats)
    ts = int(datetime.now(timezone.utc).timestamp())
    await ctx.bot.send_document(chat_id, document=html,
                                filename=f"map_{dev}_{ts}.html",
                                caption=f"🗺️ خريطة تفاعلية — {dev}\n"
                                        f"افتح الملف في المتصفح.")


async def send_stats(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    s = compute_stats(pts)
    txt = (f"📊 *إحصائيات {dev} — 24 ساعة*\n"
           f"• النقاط: `{s['points']}`\n"
           f"• المسافة: `{s['distance_km']} km`\n"
           f"• زمن الحركة: `{s['moving_time_min']} د`\n"
           f"• متوسط السرعة: `{s['avg_speed_kmh']} km/h`\n"
           f"• أقصى سرعة: `{s['max_speed_kmh']} km/h`")
    await ctx.bot.send_message(chat_id, txt, parse_mode=ParseMode.MARKDOWN)


async def send_fences(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    fences = db.get_geofences(dev)
    if not fences:
        await ctx.bot.send_message(chat_id, "🚧 لا توجد أسوار. لإضافة:\n"
                                            f"`/fence اسم خط_العرض خط_الطول نصف_القطر`")
        return
    txt = f"🚧 *أسوار {dev}:*\n" + "\n".join(
        f"• `{f['name']}` — {f['radius_m']}m — ID: `{f['id'][:8]}`" for f in fences)
    await ctx.bot.send_message(chat_id, txt, parse_mode=ParseMode.MARKDOWN)


async def send_sos(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    events = db.get_sos_events(dev, hours=48)
    if not events:
        await ctx.bot.send_message(chat_id, "🆘 لا استغاثات خلال 48 ساعة.")
        return
    for e in events[:5]:
        await ctx.bot.send_message(chat_id,
            f"🆘 *{e.get('device_id')}* — {e.get('timestamp')}\n"
            f"[📍 فتح](https://www.google.com/maps?q={e['latitude']},{e['longitude']})",
            parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ============ الأوامر النصية ============
async def cmd_fence(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    args = ctx.args
    if len(args) < 4:
        await update.message.reply_text(
            "الاستخدام: `/fence اسم خط_العرض خط_الطول نصف_القطر`\n"
            "مثال: `/fence المدرسة 33.3152 44.3661 200`",
            parse_mode=ParseMode.MARKDOWN)
        return
    name, lat, lon, r = args[0], float(args[1]), float(args[2]), float(args[3])
    dev = current_device(update.effective_chat.id)
    f = db.add_geofence(dev, name, lat, lon, r)
    await update.message.reply_text(f"✅ أُضيف سور `{f['name']}` ({r}m)", parse_mode=ParseMode.MARKDOWN)


async def cmd_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """إرسال أمر لجهاز الطفل - يُنفّذ عند عودة الاتصال"""
    if not is_owner(update):
        return
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "الأوامر المتاحة:\n"
            "`/cmd locate`  — تحديد الموقع فوراً\n"
            "`/cmd restart` — إعادة تشغيل الخدمة\n"
            "`/cmd sos_off` — إيقاف صافرة SOS\n"
            "`/cmd sync`    — مزامنة كامل البيانات",
            parse_mode=ParseMode.MARKDOWN)
        return
    dev = current_device(update.effective_chat.id)
    db.queue_command(dev, args[0], {"by": update.effective_user.id})
    await update.message.reply_text(
        f"📡 تم وضع الأمر `{args[0]}` في الطابور.\nسيُنفّذ عند عودة الاتصال.",
        parse_mode=ParseMode.MARKDOWN)




async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await reports.daily_report(ctx.bot, update.effective_chat.id)



async def send_heatmap(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, hours: int = 24):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=hours)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    html = build_heatmap_html(pts, dev)
    ts = int(datetime.now(timezone.utc).timestamp())
    await ctx.bot.send_document(
        chat_id, document=html,
        filename=f"heatmap_{dev}_{ts}.html",
        caption=f"🔥 خريطة حرارية — {dev}\nآخر {hours} ساعة"
    )


async def send_places(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24 * 7)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    places = analytics.detect_home_school(pts)
    lines = [f"🏠 *اكتشاف الأماكن — {dev}*\n"]
    if places.get("home"):
        h = places["home"]
        lines.append(f"🏠 *البيت المحتمل*\n  • {h['lat']}, {h['lon']}\n  • زيارات: {h['visits']}\n  • وقت: {h['total_minutes']} د")
    if places.get("school"):
        s = places["school"]
        lines.append(f"🏫 *المدرسة المحتملة*\n  • {s['lat']}, {s['lon']}\n  • زيارات: {s['visits']}\n  • وقت: {s['total_minutes']} د")
    if len(lines) == 1:
        lines.append("لم يتم اكتشاف أماكن متكررة بعد.")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def send_daily(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    dev = current_device(chat_id)
    pts = db.get_track(dev, hours=24)
    if not pts:
        await ctx.bot.send_message(chat_id, "⚠️ لا بيانات.")
        return
    s = analytics.daily_summary(pts)
    txt = (
        f"📅 *ملخص اليوم — {dev}*\n"
        f"• عدد النقاط: `{len(pts)}`\n"
        f"• ساعات النشاط: `{s.get('active_hours', [])}`\n"
        f"• عدد التوقفات: `{s.get('n_stops', 0)}`\n"
        f"• أول نقطة: `{s.get('first_point', '')[:19]}`\n"
        f"• آخر نقطة: `{s.get('last_point', '')[:19]}`"
    )
    await ctx.bot.send_message(chat_id, txt, parse_mode=ParseMode.MARKDOWN)


# ============ الأزرار ============
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_owner(update):
        return
    data = q.data
    chat = q.message.chat_id

    if data == "refresh":
        await q.message.reply_text("أرسل /start لاختيار الطفل.")
        return
    if data.startswith("dev:"):
        _selected[chat] = data.split(":", 1)[1]
        await q.message.reply_text(f"✅ تم اختيار: `{_selected[chat]}`. أرسل /menu.",
                                   parse_mode=ParseMode.MARKDOWN)
        return
    if data == "current":
        await send_current(chat, ctx)
    elif data == "stats":
        await send_stats(chat, ctx)
    elif data.startswith("t:"):
        await send_track(chat, ctx, int(data.split(":")[1]))
    elif data.startswith("map:"):
        await send_map(chat, ctx, int(data.split(":")[1]))
    elif data == "fences":
        await send_fences(chat, ctx)
    elif data == "sos":
        await send_sos(chat, ctx)
    elif data.startswith("heat:"):
        await send_heatmap(chat, ctx, int(data.split(":")[1]))
    elif data == "places":
        await send_places(chat, ctx)
    elif data == "daily":
        await send_daily(chat, ctx)
    elif data == "cmds":
        await q.message.reply_text(
            "📡 استخدم:\n`/cmd locate`\n`/cmd restart`\n`/cmd sync`",
            parse_mode=ParseMode.MARKDOWN)


# ============ التشغيل ============
async def post_init(app: Application):
    """تشغيل مراقب الخلفية عند الإقلاع"""
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
    app.add_handler(CommandHandler("fence", cmd_fence))
    app.add_handler(CommandHandler("cmd", cmd_command))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("heat", lambda u, c: send_heatmap(u.effective_chat.id, c, 24)))
    app.add_handler(CommandHandler("places", lambda u, c: send_places(u.effective_chat.id, c)))
    app.add_handler(CommandHandler("daily", lambda u, c: send_daily(u.effective_chat.id, c)))
    app.add_handler(CallbackQueryHandler(on_button))
    log.info("✅ Child Tracker v2.0 يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
