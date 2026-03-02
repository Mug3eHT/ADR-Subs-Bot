import os
import logging
import requests
import json
from flask import Flask, request
from datetime import date, timedelta

# ─── КОНФИГ ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8723765613:AAEq1rf8RdTYOSQtL54LKuNT70zmAwPe-Es")

BUYERS = [
    {
        "keyword": "ivan",
        "telegram_id": 8434373492,
        "name": "Ivan"
    },
    {
        "keyword": "rchq",
        "telegram_id": 8378230283,
        "name": "rchq"
    },
]

GOAL_SUBSCRIBER = ["828", "1664"]
GOAL_LEAD       = "826"
DATA_FILE       = "data.json"
# ──────────────────────────────────────────────────────────

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"counters": {}, "ad_counters": {}, "stats": {}}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"counters": counters, "ad_counters": ad_counters, "stats": stats}, f)


_data       = load_data()
counters    = _data["counters"]
ad_counters = _data["ad_counters"]
stats       = _data["stats"]


def today_str():
    return date.today().isoformat()


def yesterday_str():
    return (date.today() - timedelta(days=1)).isoformat()


def ensure_stats(name, day):
    if name not in stats:
        stats[name] = {}
    if day not in stats[name]:
        stats[name][day] = {"subscribers": 0, "leads": 0}


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
    today     = today_str()
    yesterday = yesterday_str()

    today_subs  = stats.get(name, {}).get(today, {}).get("subscribers", 0)
    today_leads = stats.get(name, {}).get(today, {}).get("leads", 0)
    yest_subs   = stats.get(name, {}).get(yesterday, {}).get("subscribers", 0)
    yest_leads  = stats.get(name, {}).get(yesterday, {}).get("leads", 0)
    all_subs    = sum(v.get("subscribers", 0) for v in stats.get(name, {}).values())
    all_leads   = sum(v.get("leads", 0) for v in stats.get(name, {}).values())

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

    name  = buyer["name"]
    today = today_str()
    ensure_stats(name, today)

    if goal in GOAL_SUBSCRIBER:
        counters[name] = counters.get(name, 0) + 1
        count = counters[name]

        ad_key = f"{name}:{ad}"
        ad_counters[ad_key] = ad_counters.get(ad_key, 0) + 1
        ad_count = ad_counters[ad_key]

        stats[name][today]["subscribers"] += 1
        save_data()

        message = (
            f"🟢 Новый подписчик! #{count}\n\n"
            f"🎯 Offer: {offer}\n"
            f"Campaign: {campaign}\n"
            f"Ad Set: {adset}\n"
            f"Ad: {ad} (+{ad_count})\n"
            f"🌍 Страна: {country}\n\n"
            f"👤 {name}"
        )
        send_message(buyer["telegram_id"], message)

    elif goal == GOAL_LEAD:
        stats[name][today]["leads"] += 1
        save_data()

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
