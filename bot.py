import os
import logging
from flask import Flask, request
from telegram import Bot
import asyncio
from datetime import datetime

# ─── КОНФИГ ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8723765613:AAEq1rf8RdTYOSQtL54LKuNT70zmAwPe-Es")

BUYERS = [
    {
        "keyword": "ivan",
        "telegram_id": 8434373492,  # Telegram ID Ивана
        "name": "Ivan"
    },
    {
        "keyword": "kamil",
        "telegram_id": 7074480840,  # Telegram ID Камиля
        "name": "Kamil"
    },
]
# ──────────────────────────────────────────────────────────

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)


def find_buyer(campaign_name: str):
    """Найти байера по ключевому слову в названии кампании"""
    if not campaign_name:
        return None
    campaign_lower = campaign_name.lower()
    for buyer in BUYERS:
        if buyer["keyword"].lower() in campaign_lower:
            return buyer
    return None


@app.route("/postback", methods=["GET", "POST"])
def postback():
    campaign = request.args.get("campaign", "")
    status = request.args.get("status", "")
    adset = request.args.get("adset", "")
    
    logging.info(f"Постбэк получен: campaign={campaign}, status={status}")

    buyer = find_buyer(campaign)

    if buyer:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        message = (
            f"🟢 Новый подписчик!\n\n"
            f"👤 Байер: {buyer['name']}\n"
            f"📢 Кампания: {campaign}\n"
            f"📊 Статус: {status}\n"
            f"🕐 Время: {now}"
        )
        asyncio.run(bot.send_message(chat_id=buyer["telegram_id"], text=message))
        logging.info(f"Уведомление отправлено байеру {buyer['name']}")
    else:
        logging.warning(f"Байер не найден для кампании: {campaign}")

    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Бот работает ✅", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
