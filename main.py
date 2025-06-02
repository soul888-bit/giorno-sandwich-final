import os
import json
import aiohttp
import nest_asyncio
import asyncio
import random
import ssl
import certifi
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

user_settings = {
    "slippage": float(os.getenv("SLIPPAGE_MAX", 4)),
    "bet": float(os.getenv("FIXED_BET", 0.2)),
    "min_swap": float(os.getenv("MIN_SWAP_AMOUNT", 0.4)),
    "min_profit": float(os.getenv("MIN_NET_PROFIT", 5)),
    "priority_fee": float(os.getenv("PRIORITY_FEE", 0.0005))
}

watched_tokens = {}
SELECTING_SETTING = 0
ssl_context = ssl.create_default_context(cafile=certifi.where())

# FastAPI app
api = FastAPI()

@api.post("/webhook")
async def webhook_listener(request: Request):
    body = await request.json()
    print("📥 Webhook reçu :", json.dumps(body, indent=2))

    for event in body:
        if event.get("type") == "SWAP":
            token = event.get("token", {}).get("mint")
            amount = float(event.get("nativeInputAmount", 0)) / 1e9

            if token in watched_tokens and watched_tokens[token]["active"]:
                if amount >= user_settings["min_swap"]:
                    message = (
                        f"🔍 Swap détecté sur {token}\n"
                        f"Montant : {amount:.2f} SOL"
                    )
                    await send_alert(message)
    return JSONResponse(content={"status": "ok"})

# Fonction d’envoi d’alerte Telegram
async def send_alert(message: str):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        await session.post(url, json=payload)

# Simulation
async def simulate_sandwich_trading():
    while True:
        await asyncio.sleep(30)
        for token_address in watched_tokens:
            if watched_tokens[token_address]["active"]:
                simulated_profit = round(random.uniform(4, 8), 2)
                if simulated_profit >= user_settings["min_profit"]:
                    message = (
                        f"🔍 Opportunité simulée trouvée sur {token_address} (test mode)\n"
                        f"🥪 (Test) Frontrun/backrun exécutés pour {token_address} – profit simulé: {simulated_profit} $"
                    )
                    await send_alert(message)

# Handlers Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        *[[InlineKeyboardButton(f"{token} : {'ON' if info['active'] else 'OFF'}", callback_data=f"toggle_{token}")]
          for token, info in watched_tokens.items()],
        [InlineKeyboardButton("Pause All", callback_data="pause_all"), InlineKeyboardButton("Resume All", callback_data="resume_all")],
        [InlineKeyboardButton("/settings", callback_data="settings")]
    ]
    await update.message.reply_text("🎛 Menu principal :", reply_markup=InlineKeyboardMarkup(keyboard))

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"Slippage max : {user_settings['slippage']}%", callback_data="slippage")],
        [InlineKeyboardButton(f"Mise fixe : {user_settings['bet']} SOL", callback_data="bet")],
        [InlineKeyboardButton(f"Swap min : {user_settings['min_swap']} SOL", callback_data="min_swap")],
        [InlineKeyboardButton(f"Profit min : {user_settings['min_profit']} $", callback_data="min_profit")],
        [InlineKeyboardButton(f"Priority fee : {user_settings['priority_fee']} SOL", callback_data="priority_fee")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text("Réglages :", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Réglages :", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_SETTING

async def setting_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['setting_to_change'] = query.data
    messages = {
        "slippage": "Changer le slippage max (%) :",
        "bet": "Changer la mise fixe (SOL) :",
        "min_swap": "Changer le montant min d’un swap ciblé (SOL) :",
        "min_profit": "Changer le profit net minimum ($) :",
        "priority_fee": "Changer la priority fee (SOL) :"
    }
    await query.edit_message_text(messages[query.data])
    return SELECTING_SETTING

async def set_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get('setting_to_change')
    value = update.message.text
    try:
        user_settings[key] = float(value)
        await update.message.reply_text(f"✅ Réglage modifié : {key} = {value}")
    except ValueError:
        await update.message.reply_text("❌ Entrée invalide.")
    return ConversationHandler.END

async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage : /add <token_address>")
        return
    token = context.args[0]
    watched_tokens[token] = {"active": True}
    await update.message.reply_text(f"✅ Token ajouté à la surveillance : {token}")

async def delete_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage : /delete <token_address>")
        return
    token = context.args[0]
    if token in watched_tokens:
        del watched_tokens[token]
        await update.message.reply_text(f"🗑 Token supprimé : {token}")
    else:
        await update.message.reply_text("❌ Token non trouvé.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watched_tokens.clear()
    await update.message.reply_text("🔁 Surveillance réinitialisée.")

async def toggle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.callback_query.data.replace("toggle_", "")
    if token in watched_tokens:
        watched_tokens[token]["active"] = not watched_tokens[token]["active"]
        await update.callback_query.answer(f"{token} {'activé' if watched_tokens[token]['active'] else 'désactivé'}")
    await start(update, context)

async def pause_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for token in watched_tokens:
        watched_tokens[token]["active"] = False
    await update.callback_query.answer("⏸ Tous les tokens mis en pause")
    await start(update, context)

async def resume_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for token in watched_tokens:
        watched_tokens[token]["active"] = True
    await update.callback_query.answer("▶️ Tous les tokens réactivés")
    await start(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start – Menu principal (affiche les tokens)\n"
        "/add <token_address> – Ajouter un token\n"
        "/delete <token_address> – Supprimer un token\n"
        "/reset – Supprimer tous les tokens surveillés\n"
        "/settings – Modifier les paramètres (slippage, mise, etc.)\n"
        "/help – Affiche ce message d'aide"
    )
    await update.message.reply_text(help_text)

# Application Telegram
telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        CallbackQueryHandler(settings, pattern="^settings$")
    ],
    states={
        SELECTING_SETTING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_value),
            CallbackQueryHandler(setting_selected)
        ]
    },
    fallbacks=[]
)

telegram_app.add_handler(conv_handler)
telegram_app.add_handler(CommandHandler("add", add_token))
telegram_app.add_handler(CommandHandler("delete", delete_token))
telegram_app.add_handler(CommandHandler("reset", reset))
telegram_app.add_handler(CommandHandler("settings", settings))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(toggle_token, pattern="^toggle_"))
telegram_app.add_handler(CallbackQueryHandler(pause_all, pattern="^pause_all$"))
telegram_app.add_handler(CallbackQueryHandler(resume_all, pattern="^resume_all$"))

nest_asyncio.apply()

async def main():
    print("✅ Giorno Sandwich Bot & Webhook démarrés")
    asyncio.create_task(simulate_sandwich_trading())
    asyncio.create_task(telegram_app.run_polling())
    config = uvicorn.Config(api, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
