import os
import logging
import requests
import psycopg2
from flask import Flask, request
from datetime import date, timedelta

# ─── КОНФИГ ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8723765613:AAEq1rf8RdTYOSQtL54LKuNT70zmAwPe-Es")
DATABASE_URL = os.environ.get("DATABASE_URL")

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

GOAL_SUBSCRIBER = "828"
GOAL_LEAD       = "826"
# ──────────────────────────────────────────────────────────

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    total INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ad_counters (
                    key TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    name TEXT,
                    day TEXT,
                    subscribers INTEGER DEFAULT 0,
                    leads INTEGER DEFAULT 0,
                    PRIMARY KEY (name, day)
                )
            """)
        conn.commit()


init_db()


def today_str():
    return date.today().isoformat()


def yesterday_str():
    return (date.today() - timedelta(days=1)).isoformat()


def increment_counter(name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO counters (name, total) VALUES (%s, 1)
                ON CONFLICT (name) DO UPDATE SET total = counters.total + 1
                RETURNING total
            """, (name,))
            result = cur.fetchone()[0]
        conn.commit()
    return result


def increment_ad_counter(key):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ad_counters (key, count) VALUES (%s, 1)
                ON CONFLICT (key) DO UPDATE SET count = ad_counters.count + 1
                RETURNING count
            """, (key,))
            result = cur.fetchone()[0]
        conn.commit()
    return result


def increment_daily(name, day, field):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO daily_stats (name, day, {field}) VALUES (%s, %s, 1)
                ON CONFLICT (name, day) DO UPDATE SET {field} = daily_stats.{field} + 1
            """, (name, day))
        conn.commit()


def get_daily(name, day):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT subscribers, leads FROM daily_stats WHERE name=%s AND day=%s", (name, day))
            row = cur.fetchone()
    return row if row else (0, 0)


def get_total(name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(subscribers),0), COALESCE(SUM(leads),0) FROM daily_stats WHERE name=%s", (name,))
            row = cur.fetchone()
    return row if row else (0, 0)


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

    today_subs, today_leads   = get_daily(name, today)
    yest_subs, yest_leads     = get_daily(name, yesterday)
    all_subs, all_leads       = get_total(name)

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

    if goal == GOAL_SUBSCRIBER:
        count    = increment_counter(name)
        ad_count = increment_ad_counter(f"{name}:{ad}")
        increment_daily(name, today, "subscribers")

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
        increment_daily(name, today, "leads")

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
