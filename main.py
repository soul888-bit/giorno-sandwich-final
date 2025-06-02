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

# Fonction d'envoi d’alerte Telegram
async def send_alert(message: str):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        await session.post(url, json=payload)

# FastAPI app (🔧 nom corrigé)
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

# Telegram Bot app
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

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

app.add_handler(conv_handler)
app.add_handler(CommandHandler("add", add_token))
app.add_handler(CommandHandler("delete", delete_token))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("settings", settings))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CallbackQueryHandler(toggle_token, pattern="^toggle_"))
app.add_handler(CallbackQueryHandler(pause_all, pattern="^pause_all$"))
app.add_handler(CallbackQueryHandler(resume_all, pattern="^resume_all$"))

nest_asyncio.apply()

async def main():
    print("✅ Giorno Sandwich Bot & Webhook démarrés")
    asyncio.create_task(simulate_sandwich_trading())
    asyncio.create_task(app.run_polling())
    config = uvicorn.Config(api, host="0.0.0.0", port=8000, loop="asyncio")  # ← use `api` ici
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())

 
