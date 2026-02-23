import os
import logging
from flask import Flask, request
from telegram import Bot
import asyncio

# ─── КОНФИГ ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8723765613:AAEq1rf8RdTYOSQtL54LKuNT70zmAwPe-Es")

BUYERS = [
    {
        "keyword": "ivan",
        "telegram_id": 8434373492,
        "name": "Ivan"
    },
    {
        "keyword": "kamil",
        "telegram_id": 7074480840,
        "name": "Kamil"
    },
]
# ──────────────────────────────────────────────────────────

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)

# Счётчик подписчиков на байера (сбрасывается при перезапуске)
counters = {}


def find_buyer(campaign_name: str):
    if not campaign_name:
        return None
    campaign_lower = campaign_name.lower()
    for buyer in BUYERS:
        if buyer["keyword"].lower() in campaign_lower:
            return buyer
    return None


GOAL_ID = "828"  # Только цель "Подписчик"


@app.route("/postback", methods=["GET", "POST"])
def postback():
    campaign = request.args.get("campaign", "")
    adset    = request.args.get("adset", "")
    ad       = request.args.get("ad", "")
    goal     = request.args.get("goal", "")

    logging.info(f"Постбэк: campaign={campaign}, adset={adset}, ad={ad}, goal={goal}")

    if goal != GOAL_ID:
        logging.info(f"Пропускаем — goal={goal}, нужен {GOAL_ID}")
        return "SKIP", 200

    buyer = find_buyer(campaign)

    if buyer:
        name = buyer["name"]
        counters[name] = counters.get(name, 0) + 1
        count = counters[name]

        message = (
            f"🟢 Новый подписчик! #{count}\n\n"
            f"Campaign: {campaign}\n"
            f"Ad Set: {adset}\n"
            f"Ad: {ad}\n\n"
            f"👤 {name}"
        )
        asyncio.run(bot.send_message(chat_id=buyer["telegram_id"], text=message))
        logging.info(f"Отправлено {name}, счётчик: {count}")
    else:
        logging.warning(f"Байер не найден: {campaign}")

    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Бот работает ✅", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
