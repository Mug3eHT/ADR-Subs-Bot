import os
import logging
import requests
from flask import Flask, request
from datetime import datetime, date
from collections import defaultdict

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

GOAL_SUBSCRIBER = "828"  # Подписчик
GOAL_LEAD       = "826"  # Лид
# ──────────────────────────────────────────────────────────

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Счётчики подписчиков на байера (общий)
counters = {}
# Счётчик на креатив
ad_counters = {}
# Статистика по дням: stats[name][date_str][goal_type] = count
stats = defaultdict(lambda: defaultdict(lambda: {"subscribers": 0, "leads": 0}))


def today_str():
    return date.today().isoformat()

def yesterday_str():
    from datetime import timedelta
    return (date.today() - timedelta(days=1)).isoformat()


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})
    logging.info(f"Telegram ответ: {resp.status_code} {resp.text}")


def find_buyer_by_campaign(campaign_name: str):
    if not campaign_name:
        return None
    campaign_lower = campaign_name.lower()
    for buyer in BUYERS:
        if buyer["keyword"].lower() in campaign_lower:
            return buyer
    return None


def find_buyer_by_chat_id(chat_id):
    for buyer in BUYERS:
        if buyer["telegram_id"] == chat_id:
            return buyer
    return None


def get_stats_message(name):
    today = today_str()
    yesterday = yesterday_str()

    today_subs  = stats[name][today]["subscribers"]
    today_leads = stats[name][today]["leads"]

    yest_subs   = stats[name][yesterday]["subscribers"]
    yest_leads  = stats[name][yesterday]["leads"]

    all_subs  = sum(v["subscribers"] for v in stats[name].values())
    all_leads = sum(v["leads"] for v in stats[name].values())

    return (
        f"📊 Статистика {name}\n\n"
        f"Сегодня:\n"
        f"  👥 Подписчики: {today_subs}\n"
        f"  💬 Лиды: {today_leads}\n\n"
        f"Вчера:\n"
        f"  👥 Подписчики: {yest_subs}\n"
        f"  💬 Лиды: {yest_leads}\n\n"
        f"За всё время:\n"
        f"  👥 Подписчики: {all_subs}\n"
        f"  💬 Лиды: {all_leads}"
    )


@app.route("/postback", methods=["GET", "POST"])
def postback():
    campaign = request.args.get("campaign", "")
    adset    = request.args.get("adset", "")
    ad       = request.args.get("ad", "")
    goal     = request.args.get("goal", "")
    country  = request.args.get("country", "—")
    offer    = request.args.get("offer", "—")

    logging.info(f"Постбэк: campaign={campaign}, goal={goal}")

    buyer = find_buyer_by_campaign(campaign)
    if not buyer:
        logging.warning(f"Байер не найден: {campaign}")
        return "OK", 200

    name = buyer["name"]
    today = today_str()

    if goal == GOAL_SUBSCRIBER:
        counters[name] = counters.get(name, 0) + 1
        count = counters[name]

        ad_key = f"{name}:{ad}"
        ad_counters[ad_key] = ad_counters.get(ad_key, 0) + 1
        ad_count = ad_counters[ad_key]

        stats[name][today]["subscribers"] += 1

        message = (
            f"🟢 Новый подписчик! #{count}\n\n"
            f"Offer: {offer}\n"
            f"Campaign: {campaign}\n"
            f"Ad Set: {adset}\n"
            f"Ad: {ad} (+{ad_count})\n"
            f"🌍 Страна: {country}\n\n"
            f"👤 {name}"
        )
        send_message(buyer["telegram_id"], message)

    elif goal == GOAL_LEAD:
        stats[name][today]["leads"] += 1
        # Лиды не шлём как отдельное уведомление — только в /stats

    return "OK", 200


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json
    if not data:
        return "OK", 200

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text    = message.get("text", "")

    if not chat_id:
        return "OK", 200

    if text == "/start":
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": chat_id,
            "text": "Привет! Нажми кнопку ниже чтобы увидеть свою статистику.",
            "reply_markup": {
                "keyboard": [[{"text": "📊 Stats"}]],
                "resize_keyboard": True,
                "persistent": True
            }
        })

    elif text in ("/stats", "📊 Stats"):
        buyer = find_buyer_by_chat_id(chat_id)
        if buyer:
            send_message(chat_id, get_stats_message(buyer["name"]))
        else:
            send_message(chat_id, "Ты не зарегистрирован в системе. Обратись к администратору.")

    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Бот работает ✅", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
