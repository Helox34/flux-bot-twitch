import asyncio
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
import main

# --- KONFIGURACJA ---
TOKEN = '8107261716:AAGiuK4z1NURsrCSplQXwhPUO--ky6IOhfk'
MY_ID = 6092966904

app_reference = None

# --- KOMENDY ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_ID: return
    welcome_msg = (
        "<b>🛸 FLUX AI - PANEL STEROWANIA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Witaj, Dowódco! System operacyjny aktywny.\n\n"
        "<b>💎 PUNKTY:</b>\n"
        "• /stats - Raport punktowy (Total + Sesja)\n\n"
        "<b>📡 MONITORING:</b>\n"
        "• /online - Kto teraz nadaje?\n"
        "• /hype - Poziom emocji na czacie\n\n"
        "<b>⚙️ USTAWIENIA:</b>\n"
        "• /list - Lista kanałów\n"
        "• /add nick - Dodaj streamera"
    )
    await update.message.reply_text(welcome_msg, parse_mode='HTML')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_ID: return
    if not app_reference:
        await update.message.reply_text("❌ <b>Błąd:</b> Brak połączenia z GUI.", parse_mode='HTML')
        return

    msg = "<b>💰 RAPORT GENEROWANIA PUNKTÓW</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    found = False
    for user, data in app_reference.streamer_stats.items():
        found = True
        total = data.get('total', '0')
        session = data.get('session', 0)
        msg += f"👤 <b>{user.upper()}</b>\n"
        msg += f"┣ 🏛️ Ogółem: <code>{total}</code>\n"
        msg += f"┗ 📈 Sesja: <b>+{session} pkt</b>\n\n"

    if not found:
        msg += "<i>Brak aktywnych danych z sesji.</i>"
    else:
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🏆 <b>SUMA SESJI:</b> <code>+{app_reference.global_session_points} pkt</code>"
    await update.message.reply_text(msg, parse_mode='HTML')

async def check_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_ID: return
    streamers = main.load_streamers()
    msg = "<b>📡 STATUSY TRANSMISJI</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for s in streamers:
        is_live = main.check_stream_status(s)
        icon = "✅ <b>ONLINE</b>" if is_live else "❌ <i>OFFLINE</i>"
        msg += f"• <b>{s}</b>: {icon}\n"
    await update.message.reply_text(msg, parse_mode='HTML')

async def hype_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_ID: return
    if app_reference and app_reference.lbl_chat:
        val = app_reference.lbl_chat.cget("text")
        await update.message.reply_text(f"🔥 <b>Aktualny Hype Score:</b> <code>{val}</code>", parse_mode='HTML')

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_ID: return
    streamers = main.load_streamers()
    msg = "<b>🎯 TWOJA LISTA FARMERSKA:</b>\n\n"
    msg += "\n".join([f"• <code>{s}</code>" for s in streamers])
    await update.message.reply_text(msg, parse_mode='HTML')

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_ID: return
    if not context.args:
        await update.message.reply_text("Użycie: /add nick")
        return
    nick = context.args[0]
    main.add_streamer_to_file(nick)
    await update.message.reply_text(f"✅ Dodano <b>{nick}</b> do bazy.", parse_mode='HTML')

# --- SILNIK URUCHAMIAJĄCY ---

def run_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = ApplicationBuilder().token(TOKEN).build()
    
# Rejestracja wszystkich komend
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('online', check_online))
    application.add_handler(CommandHandler('hype', hype_status))
    application.add_handler(CommandHandler('list', list_channels))
    application.add_handler(CommandHandler('add', add_channel))
    
    application.run_polling()

def start_telegram_thread(gui_app):
    global app_reference
    app_reference = gui_app
    t = threading.Thread(target=run_bot_loop, daemon=True)
    t.start()