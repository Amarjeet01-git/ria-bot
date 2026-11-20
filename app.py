# -*- coding: utf-8 -*-
"""
RIA BOT - 24x7 VERSION v2 (FIXED)
=================================
v2 me kya badla:
- Bot ab threaded=False hai: message aate hi handler usi time chalega,
  pehle jaise thread me atka nahi rahega.
- Webhook wala hissa seedha aur mazboot kiya: content-type ki
  nazuk shart hatayi, har message par Logs me saaf print hoga
  "WEBHOOK: message aaya" aur "HANDLER: ... chala", taaki dikkat
  turant dikh jaye.
- Koi bhi error hoga to wo Logs me poora print hoga, chhupega nahi.

Token code me NAHI hai. Render ke Environment Variable BOT_TOKEN
se aata hai, pehle jaise hi. Token badalne ki zarurat nahi hai.
"""

import io
import os
import random
import re
import time
import traceback

import requests
import telebot
from flask import Flask, request
from gtts import gTTS

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

app = Flask(__name__)


def log(*args):
    print(*args, flush=True)


if not BOT_TOKEN or ":" not in BOT_TOKEN:
    log("WARNING: BOT_TOKEN nahi mila. Render > Environment me BOT_TOKEN dalo.")

    @app.route("/")
    def home_no_token():
        return "Ria Bot: BOT_TOKEN set nahi hai. Render > Environment me BOT_TOKEN dalo.", 200

else:
    # threaded=False = handler turant, usi request me chalega
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
    BOT_USERNAME = ""
    try:
        BOT_USERNAME = bot.get_me().username.lower()
        log(f"Ria Bot Live: @{BOT_USERNAME}")
    except Exception as e:
        log("get_me fail (token check karo):", e)

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
        log("HANDLER: /start chala, chat:", m.chat.id, m.chat.type)
        bot.reply_to(
            m,
            f"Hi {first_name(m.from_user)} 👋 Main hu <b>Ria</b> 💬\n"
            "Mujhse baat karne ke liye mera naam lo ya mere message par reply karo.\n\n"
            "Fun ke liye:\n/shayari — shayari\n/joke — joke\n/truth — truth sawal\n"
            "/dare — dare challenge\n"
            "/ria apna message — jo likhoge, Ria ladki ki awaaz me bol degi 🎙️\n"
            "/help — saare commands",
        )
        log("HANDLER: /start ka reply bhej diya")

    @bot.message_handler(commands=["help"])
    def cmd_help(m):
        log("HANDLER: /help chala, chat:", m.chat.id)
        bot.reply_to(
            m,
            "<b>Ria ke commands:</b>\n/shayari — shayari\n/joke — joke\n"
            "/truth — truth\n/dare — dare\n"
            "/ria apna message — Ria use ladki ki awaaz me bol degi 🎙️\n"
            "Example: /ria Namaste doston, group me sabka swagat hai\n"
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
    #  /ria - LADKI KI AWAAZ ME BOLNA (Text-to-Speech)
    #  Example: /ria Namaste doston, group me swagat hai
    #  gTTS (Google ki free awaaz) Hindi female voice deta hai.
    # ========================================================

    @bot.message_handler(commands=["ria"])
    def cmd_ria_voice(m):
        log("HANDLER: /ria voice chala, chat:", m.chat.id, m.chat.type)
        # "/ria" ke aage wala text nikalo ("/ria@botname text" bhi chalega)
        parts = (m.text or "").split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(
                m,
                "Aise likho:\n<code>/ria Namaste doston, group me sabka swagat hai</code>\n"
                "Jo /ria ke aage likhoge, wahi main bol ke sunaungi 🎙️",
            )
            return
        text = parts[1].strip()
        if len(text) > 200:
            text = text[:200]
            bot.reply_to(m, "Message lamba tha, pehle 200 akshar hi bol rahi hu 🎙️")
        try:
            bot.send_chat_action(m.chat.id, "record_voice")
        except Exception:
            pass
        try:
            tts = gTTS(text=text, lang="hi", slow=False)
            awaaz = io.BytesIO()
            tts.write_to_fp(awaaz)
            awaaz.seek(0)
            awaaz.name = "ria_voice.mp3"
            try:
                bot.send_voice(m.chat.id, voice=awaaz, reply_to_message_id=m.message_id)
            except Exception:
                awaaz.seek(0)
                bot.send_audio(m.chat.id, audio=awaaz, reply_to_message_id=m.message_id)
            log("HANDLER: /ria voice bhej diya:", text[:40])
        except Exception:
            log("HANDLER ERROR: /ria voice fail hua, poora error neeche hai")
            traceback.print_exc()
            bot.reply_to(m, "Sorry, awaaz abhi nahi ban payi 😔 Ek baar phir try karo.")

    # ========================================================
    #  WELCOME
    # ========================================================

    @bot.message_handler(content_types=["new_chat_members"])
    def welcome(m):
        log("HANDLER: naya member aaya, chat:", m.chat.id)
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
        log("HANDLER: normal message aaya:", (m.text or "")[:40], "| chat:", m.chat.id, m.chat.type)
        if not should_reply(m):
            log("HANDLER: is message ka reply nahi karna tha (naam/tag nahi tha)")
            return
        name = first_name(m.from_user)
        try:
            bot.send_chat_action(m.chat.id, "typing")
        except Exception:
            pass
        low = m.text.lower().strip()
        if low in ["hi", "hii", "hello", "hey", "hlo", "namaste"]:
            reply = random.choice(GREET_REPLIES).replace("{name}", name)
        else:
            clean = re.sub(r"ria", "", low, flags=re.I).strip()
            if BOT_USERNAME:
                clean = clean.replace(f"@{BOT_USERNAME}", "").strip()
            reply = smart_reply(name, clean or m.text)
        bot.reply_to(m, reply)
        log("HANDLER: reply bhej diya")

    # ========================================================
    #  WEBHOOK ROUTES (v2 - mazboot)
    # ========================================================

    @app.route("/")
    def home():
        return "Ria Bot Live Hai ✅ Laptop band ho to bhi main chalti rahungi.", 200

    @app.route("/" + BOT_TOKEN, methods=["POST"])
    def webhook():
        try:
            data = request.get_json(force=True, silent=True)
            if data is None:
                raw = request.get_data(cache=False, as_text=True)
                log("WEBHOOK: JSON nahi mila, raw lamba hai:", len(raw or ""))
                import json as _json
                data = _json.loads(raw)
            update = telebot.types.Update.de_json(data)
            msg = getattr(update, "message", None)
            log(
                "WEBHOOK: update aaya, id:", update.update_id,
                "| text:", (getattr(msg, "text", None) or "")[:40] if msg else "(message nahi)",
                "| chat:", msg.chat.id if msg and msg.chat else "?",
            )
            bot.process_new_updates([update])
            log("WEBHOOK: process ho gaya, 200 bhej rahe hain")
            return "", 200
        except Exception:
            log("WEBHOOK ERROR: kuch gadbad hui, poora error neeche hai")
            traceback.print_exc()
            # Telegram ko 200 hi do taaki wo atak na jaye, error Logs me dikh gaya hai
            return "", 200

    def set_webhook():
        if RENDER_EXTERNAL_URL:
            url = RENDER_EXTERNAL_URL.rstrip("/") + "/" + BOT_TOKEN
            try:
                bot.remove_webhook()
                time.sleep(1)
                ok = bot.set_webhook(url=url)
                log("Webhook set hua:", ok, "| domain:", RENDER_EXTERNAL_URL)
            except Exception as e:
                log("Webhook set fail:", e)

    set_webhook()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
