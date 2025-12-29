#!/usr/bin/env python3
import logging
import asyncio
import sys
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Importujemy Twoją logikę z pliku main.py
# Upewnij się, że plik main.py jest w tym samym folderze!
try:
    import main
except ImportError:
    print("BŁĄD: Nie znaleziono pliku main.py! Wgraj go do tego samego folderu.")
    sys.exit(1)

# --- TWOJA KONFIGURACJA ---
TOKEN = '8107261716:AAGiuK4z1NURsrCSplQXwhPUO--ky6IOhfk'
AUTHORIZED_USER_ID = 6092966904  # Twój ID, bot słucha tylko Ciebie

# Inicjalizacja koparki (Minera)
miner_instance = main.PointMiner()

# Konfiguracja logowania (widoczne w terminalu Della)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- ZABEZPIECZENIA ---
def is_authorized(update: Update):
    """Sprawdza, czy komendę wysyłasz Ty."""
    user = update.effective_user
    if user.id == AUTHORIZED_USER_ID:
        return True
    else:
        print(f"⚠️ Nieautoryzowana próba dostępu od ID: {user.id} ({user.first_name})")
        return False

# --- KOMENDY TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    msg = (
        "🚀 **Flux Server (Dell Wyse)** jest ONLINE!\n\n"
        "Lista komend:\n"
        "⛏️ /mine - Uruchom koparkę (zbieranie punktów)\n"
        "📊 /status - Sprawdź kto jest LIVE\n"
        "📝 /list - Pokaż listę streamerów\n"
        "➕ /add [nick] - Dodaj streamera\n"
        "➖ /remove [nick] - Usuń streamera\n"
        "❓ /help - Pokaż to menu"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    await update.message.reply_text("⛏️ Uruchamiam proces kopania w tle...")
    # Uruchomienie w sposób bezpieczny dla wątków
    try:
        miner_instance.start()
        await update.message.reply_text("✅ Koparka działa! Zbieram punkty.")
    except Exception as e:
        await update.message.reply_text(f"❌ Błąd podczas startu koparki: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    await update.message.reply_text("⏳ Sprawdzam statusy streamerów, chwileczkę...")
    streamers = main.load_streamers()
    
    if not streamers:
        await update.message.reply_text("📭 Lista streamerów jest pusta.")
        return

    msg = "📊 **Status Farmy:**\n"
    online_count = 0
    
    for s in streamers:
        try:
            is_live = main.check_stream_status(s)
            if is_live:
                icon = "🟢 **ONLINE**"
                online_count += 1
            else:
                icon = "🔴 OFF"
            msg += f"{icon} - {s}\n"
        except Exception as e:
            msg += f"⚠️ Błąd - {s}\n"

    summary = f"\nAktywnych: {online_count} / {len(streamers)}"
    await update.message.reply_text(msg + summary, parse_mode='Markdown')

async def list_streamers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    streamers = main.load_streamers()
    if streamers:
        msg = f"📝 **Twoja lista:**\n{', '.join(streamers)}"
    else:
        msg = "📭 Lista jest pusta."
    await update.message.reply_text(msg, parse_mode='Markdown')

async def add_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    if not context.args:
        await update.message.reply_text("❌ Podaj nick! Przykład: `/add xayoo_`", parse_mode='Markdown')
        return
    
    nick = context.args[0].lower()
    if main.add_streamer_to_file(nick):
        await update.message.reply_text(f"✅ Dodano **{nick}** do listy.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ **{nick}** już jest na liście.", parse_mode='Markdown')

async def remove_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    
    if not context.args:
        await update.message.reply_text("❌ Podaj nick! Przykład: `/remove xayoo_`", parse_mode='Markdown')
        return
    
    nick = context.args[0].lower()
    if main.remove_streamer_from_file(nick):
        await update.message.reply_text(f"🗑️ Usunięto **{nick}** z listy.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ Nie znaleziono **{nick}** na liście.", parse_mode='Markdown')

# --- URUCHOMIENIE ---

if __name__ == '__main__':
    try:
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('help', start))
        app.add_handler(CommandHandler('mine', mine))
        app.add_handler(CommandHandler('status', status))
        app.add_handler(CommandHandler('list', list_streamers))
        app.add_handler(CommandHandler('add', add_streamer))
        app.add_handler(CommandHandler('remove', remove_streamer))
        
        print("🤖 Flux Bot (Server) jest gotowy i nasłuchuje...")
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Błąd krytyczny: {e}")