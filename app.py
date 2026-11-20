# -*- coding: utf-8 -*-
"""
RIA BOT - 24x7 WALA VERSION (Render par chalega)
=================================================
Laptop band ho jaye to bhi bot chalti rahegi, kyunki ye
tumhare laptop par nahi, Render ke server par chalegi.

Token code me NAHI likhna hai.
Token Render ki website par "Environment Variable" me dalega:
    Name:  BOT_TOKEN
    Value: BotFather se mila token

Optional smart AI ke liye wahi ek aur variable:
    Name:  OPENROUTER_API_KEY
    Value: openrouter.ai se mili free key (na ho to mat dalo)
"""

import os
import random
import re
import time

import requests
import telebot
from flask import Flask, request

# ============================================================
#  TOKEN - Render se milega
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

app = Flask(__name__)

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    print("WARNING: BOT_TOKEN nahi mila. Render me Environment Variable dalo.")

    @app.route("/")
    def home_no_token():
        return "Ria Bot: BOT_TOKEN set nahi hai. Render > Environment me BOT_TOKEN dalo.", 200

else:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    BOT_USERNAME = ""
    try:
        BOT_USERNAME = bot.get_me().username.lower()
        print(f"Ria Bot Live: @{BOT_USERNAME}")
    except Exception as e:
        print("get_me fail (token check karo):", e)

    # ========================================================
    #  FUN DATA
    # ========================================================

    SHAYARI = [
        "Mohabbat me jhukna koi ajeeb baat nahi,\nSuraj bhi dhal jata hai chaand ke liye.",
        "Teri yaadon ka nasha kuch aisa hai,\nNeend aati hai magar dil sona nahi chahta.",
        "Hum to haste hain dusro ko hasane ke liye,\nWarna dil me dard itna hai ki rona bhi nahi aata.",
        "Kuch log dil me aise utar jate hain,\nJinke nikalne se jaan nikal jati hai.",
        "Waqt sikha deta hai jeene ka hunar,\nPhir kismat se ladna bhi aa jata hai.",
    ]

    JOKES = [
        "Teacher: Batao chaand par pehla kadam kisne rakha?\nStudent: Neil Armstrong.\nTeacher: Aur dusra?\nStudent: Wahi, dusra pair bhi usi ka tha sir 😂",
        "Doctor: Tumhe roz exercise karni chahiye.\nPatient: Main roz karta hu sir.\nDoctor: Kya?\nPatient: Dimag ladana aur baatein ghumana 😜",
    ]

    TRUTH = [
        "Group me sabse pehle crush kisko hua tha? Sach batao 👀",
        "Apna sabse embarrassing moment batao.",
        "Last time jhooth kab aur kyu bola tha?",
        "Phone me sabse chhupa ke rakhi cheez kya hai?",
    ]

    DARE = [
        "Apni gallery ki 5th photo group me bhejo (safe wali) 😜",
        "Apne best friend ko voice note me gaana gaa ke bhejo.",
        "Agle 10 minute apne naam ke aage 'Don' laga ke chat karo.",
        "Group ke kisi ek bande ki funny tareef 3 line me karo.",
    ]

    GREET_REPLIES = [
        "Hii {name} 😊 main Ria, bolo kya chal raha hai group me?",
        "Hello hello {name}! Aaj mood kaisa hai?",
        "Haa {name}, main sun rahi hu, bolo bolo 👀",
    ]

    KEYWORD_REPLIES = [
        (["kaise ho", "kaisi ho", "how are you"], ["Main badhiya hu {name}, tum sunao?", "Main mast hu! Tumhara din kaisa gaya?"]),
        (["shayari", "sher"], SHAYARI),
        (["joke", "hasao", "funny"], JOKES),
        (["bye", "good night", "gn", "alvida"], ["Bye bye {name}, dhyan rakhna apna 🌙", "Good night {name}, kal phir baat hogi!"]),
        (["thank", "shukriya", "dhanyavad"], ["Arey koi baat nahi {name} 😊", "Welcome welcome! Main hu na help ke liye."]),
        (["bore", "boring", "maza nahi"], ["Bore ho rahe ho? /truth ya /dare likho, game shuru karte hain 😜", "Chalo mood banate hain - /joke likho pehle!"]),
        (["khana", "bhook", "hungry"], ["Bhook lagi hai {name}? Kuch achha kha lo, phir energy aayegi 😋"]),
        (["love", "pyar", "pyaar", "crush"], ["Ohooo {name}, pyar wala mood hai aaj 👀", "Pyar khoobsurat hai, bas sahi insaan se ho ❤️"]),
        (["sad", "dukhi", "pareshan", "tension"], ["Pareshan mat ho {name}, waqt badalta hai. Baat karo, halka lagega 🤗", "Main hu na {name}, bolo kya hua?"]),
        (["game", "khel"], ["Game ka mood hai? Group me @gamee ya @unobot likho, ya /truth /dare khelo!"]),
        (["music", "gaana", "song"], ["Gaane ka mood hai 🎵 Apna favourite gaana group me share karo!"]),
    ]

    DEFAULT_REPLIES = [
        "Hmm {name}, interesting baat hai 👀 Aur batao?",
        "Achha achha, samajh gayi {name} 😊 Phir kya hua?",
        "Sahi bola {name}! Bore ho to /joke ya /shayari likho",
        "Haha {name}, tumhari baatein mazedaar hain 😜",
        "Bolo bolo {name}, main sun rahi hu...",
    ]

    def ai_reply(user_name, user_text):
        if not OPENROUTER_API_KEY:
            return None
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Tum Ria ho, ek friendly ladki jo Telegram group me "
                                "Hinglish (Hindi Roman + thodi English) me chhote, "
                                "mazedaar aur dostana reply deti hai. Reply 1-2 line "
                                "ka hi rakho. Gali mat do, sabse respect se baat karo."
                            ),
                        },
                        {"role": "user", "content": f"{user_name} bola: {user_text}"},
                    ],
                },
                timeout=15,
            )
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    def smart_reply(name, text):
        ai = ai_reply(name, text)
        if ai:
            return ai
        low = text.lower()
        for keywords, replies in KEYWORD_REPLIES:
            if any(k in low for k in keywords):
                return random.choice(replies).replace("{name}", name)
        return random.choice(DEFAULT_REPLIES).replace("{name}", name)

    def first_name(user):
        return (user.first_name or "Dost").strip()

    # ========================================================
    #  COMMANDS
    # ========================================================

    @bot.message_handler(commands=["start"])
    def cmd_start(m):
        bot.reply_to(
            m,
            f"Hi {first_name(m.from_user)} 👋 Main hu <b>Ria</b> 💬\n"
            "Mujhse baat karne ke liye mera naam lo ya mere message par reply karo.\n\n"
            "Fun ke liye:\n/shayari — shayari\n/joke — joke\n/truth — truth sawal\n"
            "/dare — dare challenge\n/help — saare commands",
        )

    @bot.message_handler(commands=["help"])
    def cmd_help(m):
        bot.reply_to(
            m,
            "<b>Ria ke commands:</b>\n/shayari — shayari\n/joke — joke\n"
            "/truth — truth\n/dare — dare\n"
            "Baat karne ke liye bas 'Ria' likho ya mere message par reply karo 😊",
        )

    @bot.message_handler(commands=["shayari"])
    def cmd_shayari(m):
        bot.reply_to(m, random.choice(SHAYARI))

    @bot.message_handler(commands=["joke"])
    def cmd_joke(m):
        bot.reply_to(m, random.choice(JOKES))

    @bot.message_handler(commands=["truth"])
    def cmd_truth(m):
        bot.reply_to(m, "🔥 <b>Truth:</b> " + random.choice(TRUTH))

    @bot.message_handler(commands=["dare"])
    def cmd_dare(m):
        bot.reply_to(m, "😈 <b>Dare:</b> " + random.choice(DARE))

    # ========================================================
    #  WELCOME
    # ========================================================

    @bot.message_handler(content_types=["new_chat_members"])
    def welcome(m):
        for user in m.new_chat_members:
            if BOT_USERNAME and user.username and user.username.lower() == BOT_USERNAME:
                bot.send_message(
                    m.chat.id,
                    "Hi sabko 👋 Main <b>Ria</b> aa gayi hu is group me!\n"
                    "Mera naam likho ya mere message par reply karo, main jawab dungi.\n"
                    "Fun ke liye /shayari /joke /truth /dare try karo 😊",
                )
            else:
                bot.send_message(
                    m.chat.id,
                    f"Welcome {first_name(user)} 🎉 Group me tumhara swagat hai!\n"
                    "Main Ria hu, yaha ki dost. Rules padh lo aur maze karo 😊",
                )

    # ========================================================
    #  NORMAL CHAT
    # ========================================================

    def should_reply(m):
        if m.chat.type == "private":
            return True
        text = (m.text or "").lower()
        if "ria" in text:
            return True
        if BOT_USERNAME and f"@{BOT_USERNAME}" in text:
            return True
        if m.reply_to_message and m.reply_to_message.from_user:
            sender = m.reply_to_message.from_user
            if sender.is_bot and BOT_USERNAME and sender.username and sender.username.lower() == BOT_USERNAME:
                return True
        if text.strip() in ["hi", "hii", "hello", "hey", "hlo"]:
            return True
        return False

    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/"))
    def chat_reply(m):
        if not should_reply(m):
            return
        name = first_name(m.from_user)
        try:
            bot.send_chat_action(m.chat.id, "typing")
        except Exception:
            pass
        time.sleep(random.uniform(0.5, 1.2))
        low = m.text.lower().strip()
        if low in ["hi", "hii", "hello", "hey", "hlo", "namaste"]:
            reply = random.choice(GREET_REPLIES).replace("{name}", name)
        else:
            clean = re.sub(r"ria", "", low, flags=re.I).strip()
            if BOT_USERNAME:
                clean = clean.replace(f"@{BOT_USERNAME}", "").strip()
            reply = smart_reply(name, clean or m.text)
        bot.reply_to(m, reply)

    # ========================================================
    #  WEBHOOK ROUTES (Render ke liye)
    # ========================================================

    @app.route("/")
    def home():
        return "Ria Bot Live Hai ✅ Laptop band ho to bhi main chalti rahungi.", 200

    @app.route("/" + BOT_TOKEN, methods=["POST"])
    def webhook():
        if request.headers.get("content-type") == "application/json":
            update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
            bot.process_new_updates([update])
            return "", 200
        return "Bad request", 403

    def set_webhook():
        if RENDER_EXTERNAL_URL:
            url = RENDER_EXTERNAL_URL.rstrip("/") + "/" + BOT_TOKEN
            try:
                bot.remove_webhook()
                time.sleep(1)
                bot.set_webhook(url=url)
                print("Webhook set:", RENDER_EXTERNAL_URL)
            except Exception as e:
                print("Webhook set fail:", e)

    set_webhook()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
