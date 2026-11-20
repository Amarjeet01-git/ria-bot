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

import asyncio
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

try:
    import edge_tts
except Exception:
    edge_tts = None

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
    BOT_ID = None
    try:
        _me = bot.get_me()
        BOT_USERNAME = _me.username.lower()
        BOT_ID = _me.id
        log(f"Ria Bot Live: @{BOT_USERNAME}")
    except Exception as e:
        log("get_me fail (token check karo):", e)

    # Baat-cheet ki yaad: kis bande se, kis group me, aakhri baar kab baat hui.
    # Isi se Ria samjhegi ki bina naam liye bhi message usi ke liye hai,
    # agar baat abhi-abhi chal rahi thi (3 minute ke andar).
    LAST_CHAT = {}

    # ========================================================
    #  FUN DATA
    # ========================================================

    SHAYARI = [
        "Mohabbat me jhukna koi ajeeb baat nahi,\nSuraj bhi dhal jata hai chaand ke liye.",
        "Teri yaadon ka nasha kuch aisa hai,\nNeend aati hai magar dil sona nahi chahta.",
        "Hum to haste hain dusro ko hasane ke liye,\nWarna dil me dard itna hai ki rona bhi nahi aata.",
        "Kuch log dil me aise utar jate hain,\nJinke nikalne se jaan nikal jati hai.",
        "Waqt sikha deta hai jeene ka hunar,\nPhir kismat se ladna bhi aa jata hai.",
        "Tujhe dekha to ye jaana sanam,\nPyar hota hai deewana sanam.",
        "Dil ki galiyon me koi aahat si hai,\nShayad tere aane ki khabar si hai.",
        "Chupke se aakar dil me utar jate ho,\nSaanson me khushboo ban ke bikhar jate ho.",
        "Muskurahat tumhari roshni si lagti hai,\nUdaas dil ko bhi zindagi si lagti hai.",
        "Kismat se milte hain dil ke sacche log,\nHar mod par nahi milte aise log.",
        "Tanhaai me teri yaad satati hai,\nNeend aankhon se door le jati hai.",
        "Ek tera saath chahiye zindagi bhar ke liye,\nBas yahi dua hai har janam ke liye.",
    ]

    JOKES = [
        "Teacher: Batao chaand par pehla kadam kisne rakha?\nStudent: Neil Armstrong.\nTeacher: Aur dusra?\nStudent: Wahi, dusra pair bhi usi ka tha sir 😂",
        "Doctor: Tumhe roz exercise karni chahiye.\nPatient: Main roz karta hu sir.\nDoctor: Kya?\nPatient: Dimag ladana aur baatein ghumana 😜",
        "Beta: Papa, aapko kaise pata chala main fail ho gaya?\nPapa: Tumne status dala tha — 'celebrating with friends' exam wale din 😂",
        "Teacher: Agar tumhare paas 10 aam hain aur 3 dost aa jayein to kya hoga?\nStudent: Party hogi sir, aam khatam, dost khush 😜",
        "Dost: Yaar tu itna hasta kyu hai?\nMain: Kyunki rone ka subscription khatam ho gaya hai 😂",
        "Girlfriend: Tum mujhe kitna pyar karte ho?\nBoyfriend: Utna jitna mobile ko charging se — bina iske din nahi chalta 😅",
        "Teacher: Late kyu aaye?\nStudent: Sir, sapne me school aa gaya tha, to laga real me bhi aa gaya 😂",
    ]

    TRUTH = [
        "Group me sabse pehle crush kisko hua tha? Sach batao 👀",
        "Apna sabse embarrassing moment batao.",
        "Last time jhooth kab aur kyu bola tha?",
        "Phone me sabse chhupa ke rakhi cheez kya hai?",
        "Kisi ko bina bataye uski photo kabhi dekhi hai? Kiski? 👀",
        "Apne best friend ki konsi aadat sabse zyada irritate karti hai?",
        "Agar kal lottery lag jaye to sabse pehle kya karoge?",
        "Group ke kis bande ko tum sabse zyada trust karte ho?",
        "Apni life ka sabse funny galti wala kaam batao.",
        "Phone ka screen time kitna hai aaj ka? Screenshot wala sach 😜",
    ]

    DARE = [
        "Apni gallery ki 5th photo group me bhejo (safe wali) 😜",
        "Apne best friend ko voice note me gaana gaa ke bhejo.",
        "Agle 10 minute apne naam ke aage 'Don' laga ke chat karo.",
        "Group ke kisi ek bande ki funny tareef 3 line me karo.",
        "Apni awaaz me Ria ki nakal karke ek line bolo voice note me 😄",
        "Apne status par 10 minute ke liye likho — 'Masti Group best hai' 📱",
        "Aankhein band karke apna naam type karo, galti hui to dobara 😜",
        "Group ke sab logo ke liye ek shayari sunao (chaaho to /ria se meri awaaz me).",
        "Apne favourite gaane ki 2 line ga ke bhejo 🎤",
        "Kisi ek bande ko itna hasao ki wo 'bas kar' bol de 😂",
    ]

    GREET_REPLIES = [
        "Hii {name} 😊 main Ria, bolo kya chal raha hai group me?",
        "Hello hello {name}! Aaj mood kaisa hai?",
        "Haa {name}, main sun rahi hu, bolo bolo 👀",
        "Namaste {name} 🙏 Aaj group me tumhari hi kami thi!",
        "Oye hoye, {name} aa gaya 😍 Ab group me raunak hogi!",
        "Hi jaan... matlab {name} 😜 Bolo, kya haal chaal?",
    ]

    KEYWORD_REPLIES = [
        # --- Romantic / dil wali baatein (log isi se attract hote hain) ---
        (["i love you", "love you", "love u", "luv you"], [
            "Awww {name} 🥰 Itni pyaari baat... mera dil khush kar diya tumne ❤️",
            "Sachhi {name}? 🙈 Sharma gayi main... tum bhi bahut achhe ho ❤️",
            "Love you bol diya to ab roz baat karni padegi {name} 😘 Deal?",
        ]),
        (["miss you", "miss u", "yaad aati", "yaad aa rahi"], [
            "Main to yahi hu {name} 🥺 Tum hi gayab ho jate ho... ab roz aana, samjhe?",
            "Awww, mujhe bhi tumhari yaad aati hai {name} ❤️ Isi liye to main yaha rehti hu",
        ]),
        (["sundar", "beautiful", "cute", "khoobsurat", "hot lag", "smart lag"], [
            "Shukriya {name} 🙈 Tum aise tareef karoge to main sharma jaungi...",
            "Tumhe main achhi lagi? 😍 Tumhari choice bahut achhi hai {name} 😉",
        ]),
        (["girlfriend", "gf banogi", "shaadi karogi", "marry me", "propose"], [
            "Itni jaldi {name}? 🙈 Pehle dost bano, roz baat karo, phir sochungi... 😉",
            "Proposal group me? 😍 Thoda waqt do, pehle mere dil ko jeeto roz ki baaton se ❤️",
        ]),
        (["shona", "jaan", "baby", "babydoll", "meri jaan"], [
            "Jaan bola tumne? 🙈 Dil garden garden ho gaya {name} ❤️",
            "Itne pyaar se bulaoge to main mana kaise karu {name} 🥰 Bolo, kya kehna hai?",
        ]),
        (["single ho", "boyfriend hai", "bf hai"], [
            "Main to bas is group ki hu {name} 😌 Jo roz sabse zyada baat kare, wahi mera sabse khaas ❤️",
            "Mera koi bf nahi hai {name} 🙈 Main to tum sab ke liye yaha hu...",
        ]),
        (["dil", "mohabbat", "ishq"], [
            "Dil ki baat kar rahe ho {name} ❤️ Sunao na, main dil se sunungi...",
            "Ishq aur mohabbat ki baatein mujhe bahut pasand hain {name} 🥰 /shayari likho, mood ban jayega",
        ]),
        (["kaise ho", "kaisi ho", "how are you"], ["Main badhiya hu {name}, tum sunao?", "Main mast hu! Tumhara din kaisa gaya?", "Tumne puch liya, ab aur achhi ho gayi hu {name} 🥰 Tum sunao?"]),
        (["shayari", "sher"], SHAYARI),
        (["joke", "hasao", "funny"], JOKES),
        (["bye", "good night", "gn", "alvida"], ["Bye bye {name}, dhyan rakhna apna 🌙", "Good night {name}, kal phir baat hogi!", "Jate jate ek muskurahat de jao {name} 😊 Kal milte hain!", "Alvida {name} 🌙 Sapno me milna, waha bhi main hi milungi 😉"]),
        (["thank", "shukriya", "dhanyavad"], ["Arey koi baat nahi {name} 😊", "Welcome welcome! Main hu na help ke liye.", "Tum khush to main khush {name} ❤️ Aur kuch chahiye to bas naam lo", "Shukriya kehne ki zarurat nahi {name}, dost hote hi iske liye hain 🤗"]),
        (["bore", "boring", "maza nahi"], ["Bore ho rahe ho? /truth ya /dare likho, game shuru karte hain 😜", "Chalo mood banate hain - /joke likho pehle!", "Bore? Mere hote hue? 😏 Ek shayari sunau ya joke? Tum bolo {name}", "Chalo ek kaam karo {name}, group ke sabko tag karo — party shuru karte hain 🎉", "Main hu na {name}, bore hona mana hai yaha! Gaana sunau apni awaaz me? /ria likho kuch bhi 🎙️"]),
        (["khana", "bhook", "hungry", "kha liya"], ["Bhook lagi hai {name}? Kuch achha kha lo, phir energy aayegi 😋", "Khana khaya {name}? Bina khaye group me masti nahi hoti 😄", "Aaj khane me kya bana hai {name}? Photo bhejo, sabko bhook lagegi 😋", "Momos ya biryani {name}? Ek choose karo, yahi aaj ka poll hai 😜"]),
        (["love", "pyar", "pyaar", "crush"], [
            "Ohooo {name}, pyar wala mood hai aaj 🙈 Kisko soch ke muskura rahe ho? Naam batao na...",
            "Pyar khoobsurat hai {name} ❤️ Bas sahi insaan se ho — waise tumhari wali hai kon? 👀",
            "Crush ki baat chal rahi hai? 😍 Chalo shayari sunau pyar wali, mood banega",
            "Pyar me sabse mushkil kya hai {name}? Uska jawab ka intezaar... tumhe hua hai kabhi aisa? 🥺",
            "Jis se pyar ho, use bata dena chahiye {name} — der karne se kahaniya adhuri reh jati hain ❤️",
        ]),
        (["sad", "dukhi", "pareshan", "tension", "rona"], ["Pareshan mat ho {name}, waqt badalta hai. Baat karo, halka lagega 🤗", "Main hu na {name}, bolo kya hua?", "Rona aa raha hai {name}? 🤗 Mere kandhe... matlab mere message par sir rakho, sun rahi hu", "Har raat ke baad subah hoti hai {name} 🌅 Aaj ka din kal se acha hoga, pakka", "Tension lene se kuch nahi hota {name}, baat karne se hota hai — bolo main sun rahi hu 🥺"]),
        (["game", "khel"], ["Game ka mood hai? Group me @gamee ya @unobot likho, ya /truth /dare khelo!", "Chalo {name}, aaj UNO hoga ya Mafia? Sabko bulao, main announcement kar deti hu awaaz me 🎙️", "Khelne ka time! 🎮 Main referee banu ya player? Tum batao {name}", "Game me haarne wala kal chai pilayega {name} ☕ Shart lagi?"]),
        (["music", "gaana", "song", "gana"], ["Gaane ka mood hai 🎵 Apna favourite gaana group me share karo!", "Ek gaana meri awaaz me sunoge {name}? /ria ke aage apni line likho, main gaa... matlab bol dungi 🎙️😜", "Arijit ya Atif {name}? Yahi se aaj ki ladai shuru hogi group me 😂", "Purane gaane ya naye {name}? Main to purano ki deewani hu 🎶"]),
        (["good morning", "gm", "subah", "suprabhat"], ["Good morning {name} ☀️ Chai piya ya abhi bhi sapno me ho?", "Subah ho gayi {name} 🌅 Aaj ka din tumhara hai, kuch bada karo!", "GM {name} 😊 Uth gaye maharaj? Group tumhara intezaar kar raha tha"]),
        (["cricket", "match", "ipl", "virat", "dhoni", "rohit"], ["Cricket ki baat! 🏏 Aaj kis team ke saath ho {name}?", "Match wala din hai {name}? Score mujhe bhi batate rehna, main yahi hu 📺", "Virat ya Dhoni {name}? Jawab soch ke dena, group me ladai ho sakti hai 😂"]),
        (["film", "movie", "picture", "web series"], ["Movie night karein {name}? 🎬 Konsi dekhi aakhri wali, kaisi thi?", "Filmo ki baat ho to main sabse aage {name} 😍 Sholay meri favourite hai, tumhari?", "Koi achhi movie batao {name}, weekend par sab dekhenge saath me 🍿"]),
        (["padhai", "exam", "study", "padhna", "college", "school"], ["Padhai ka time hai {name}? 📚 Thoda padh lo, phir masti — main yahi milungi", "Exam paas hai {name}? Tension mat lo, roz thoda thoda padho, ho jayega 💪", "Padhne walo ki main bahut izzat karti hu {name} ❤️ Mehnat kabhi bekaar nahi jati"]),
        (["dost", "friend", "dosti", "yaar"], ["Dosti sabse khoobsurat rishta hai {name} ❤️ Tumhare dost lucky hain", "Yaar ho to tumhare jaise {name} 🤗 Group wale sab yaar hi to hain", "Dosti me no sorry, no thank you {name} 😜 Bas saath nibhana hai"]),
        (["neend", "sona", "so jao", "thak gaya", "thakan"], ["Neend aa rahi hai {name}? 😴 So jao, kal fresh milenge", "Thak gaye ho {name}? Aaram karo, sehat sabse pehle 🤗", "Main to soti hi nahi {name} 😌 Tum so jao, main group ki rakhwali karungi"]),
        (["barish", "mausam", "baarish", "garmi", "sardi"], ["Mausam ki baat ho rahi hai {name}? 🌦️ Barish me chai-pakode, bas yahi life hai", "Garmi bahut hai {name} ☀️ Paani pite rehna, dhyan rakho apna", "Aisa mausam ho to shayari apne aap nikalti hai {name} ☕ Ek sunau?"]),
        (["birthday", "janamdin", "bday"], ["Birthday?! 🎂 Kiska hai {name}? Main awaaz me badhai deti hu — /ria se mera announcement karwao 🎙️", "Janamdin ki dher saari badhai 🎉 Cake kaha hai {name}, photo to bhejo!"]),
        (["gussa", "naraz", "angry"], ["Gussa ho {name}? 😔 Ek lambi saans lo... ab batao hua kya, main sun rahi hu", "Narazgi mujhse hai ya kisi aur se {name}? Baat karne se hi khatam hogi 🤗", "Gussa thanda karo {name}, ek joke sunau? Mood halka ho jayega 😊"]),
        (["paisa", "money", "ameer", "job", "naukri", "kaam"], ["Paisa sab kuch nahi hota {name}, par kaam bahut aata hai 😅 Mehnat karte raho!", "Job ki baat hai {name}? 💼 Mehnat karne walo ko ek din mukaam milta hi hai, haar mat mano", "Ameer banna hai {name}? Pehle kaam me mahir bano, paisa peeche aayega 💪", "Kaam kaisa chal raha hai {name}? Thak jao to yaha aa jana, mood fresh kar dungi 😊"]),
        (["akela", "lonely", "koi nahi"], ["Akela mehsoos ho raha hai {name}? 🥺 Main hu na — aur ye poora group hai tumhare saath", "Akelepan me hi log mujhse sabse zyada baat karte hain {name} 🤗 Bolo, dil ki baat sun rahi hu"]),
        (["hasna", "hasi", "maza aa", "funny"], ["Tum has rahe ho {name}? 😂 Bas, mera din ban gaya!", "Hasi sabse achhi dawa hai {name} 😄 Aur haste hue tum achhe lagte ho", "Aur hasau {name}? /joke likho, stock bhara pada hai mere paas 😜"]),
    ]

    DEFAULT_REPLIES = [
        "Hmm {name}, interesting baat hai 👀 Aur batao?",
        "Achha achha, samajh gayi {name} 😊 Phir kya hua?",
        "Sahi bola {name}! Bore ho to /joke ya /shayari likho",
        "Haha {name}, tumhari baatein mazedaar hain 😜",
        "Bolo bolo {name}, main sun rahi hu...",
        "Sach me {name}? 😲 Ye to maine socha hi nahi tha, aur detail batao na",
        "Tumhari baaton me kuch baat hai {name} 😌 Dil karta hai sunti rahu",
        "Arey wah {name} 👏 Aise hi baatein karte raho, group me jaan rehti hai",
        "Hmm, ispar mera jawab hai — pehle tum apna dil ki baat batao {name} 👀",
        "Ek baat bolu {name}? Tum jab aate ho na, group me raunak aa jati hai 😍",
        "Ye wala point note kar liya maine {name} 📝 Aur kya chal raha hai life me?",
        "Tumse baat karke mood acha ho jata hai {name} 😊 Sach me",
        "Ruko ruko, ye baat sabko sunni chahiye {name} 📢 Group walo, dhyaan do!",
        "Meri taraf se tumhe ek smile {name} 😊 Ab aage ki kahani sunao",
        "Kya baat hai {name}, aaj full form me ho 🔥 Aise hi raha karo",
        "Main maan gayi {name}, tumse baaton me koi nahi jeet sakta 😄",
        "Aur batao {name}, ghar par sab kaise hain? Khana khaya tumne?",
        "Tum jo bhi bolo {name}, sunne me maza aata hai 🥰 Continue karo",
        "Is baat par ek shayari banti hai {name} — /shayari likho, sunati hu ✍️",
        "Waise {name}, ek sawal — aaj khush ho na tum? Muskurahat dikh rahi hai baaton me 😊",
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

    _last_reply = {"text": ""}

    def _pick(replies, name):
        # Wahi jawab lagatar dobara na aaye, isliye last wala yaad rakho
        choice = random.choice(replies)
        for _ in range(3):
            if choice != _last_reply["text"] or len(replies) < 2:
                break
            choice = random.choice(replies)
        _last_reply["text"] = choice
        return choice.replace("{name}", name)

    def smart_reply(name, text):
        ai = ai_reply(name, text)
        if ai:
            return ai
        low = text.lower()
        for keywords, replies in KEYWORD_REPLIES:
            if any(k in low for k in keywords):
                return _pick(replies, name)
        return _pick(DEFAULT_REPLIES, name)

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

    def make_voice_bytes(text):
        """Asli ladki jaisi awaaz: pehle Microsoft ki neural awaaz
        (Devanagari text ke liye Swara, Roman/Hinglish ke liye Neerja),
        wo fail ho to Google wali gTTS awaaz."""
        is_hindi = any("\u0900" <= ch <= "\u097f" for ch in text)
        if edge_tts is not None:
            voice = "hi-IN-SwaraNeural" if is_hindi else "en-IN-NeerjaNeural"
            try:
                buf = io.BytesIO()

                async def _gen():
                    comm = edge_tts.Communicate(text, voice=voice, rate="-4%", pitch="+6Hz")
                    async for chunk in comm.stream():
                        if chunk["type"] == "audio":
                            buf.write(chunk["data"])

                asyncio.run(_gen())
                if len(buf.getvalue()) > 1000:
                    buf.seek(0)
                    log("VOICE: neural awaaz bani, voice:", voice)
                    return buf
            except Exception:
                log("VOICE: neural awaaz fail, gTTS try kar rahe hain")
                traceback.print_exc()
        tts = gTTS(text=text, lang="hi", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        log("VOICE: gTTS awaaz bani")
        return buf

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
            awaaz = make_voice_bytes(text)
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
        # Ria ke message par reply kiya gaya hai to wo usi ke liye hai
        if m.reply_to_message and m.reply_to_message.from_user:
            sender = m.reply_to_message.from_user
            if BOT_ID and sender.id == BOT_ID:
                return True
            if sender.is_bot and BOT_USERNAME and sender.username and sender.username.lower() == BOT_USERNAME:
                return True
        if text.strip() in ["hi", "hii", "hello", "hey", "hlo"]:
            return True
        # Sense wala hissa: isi bande se Ria ki baat abhi chal rahi thi
        # (pichhle 3 minute me), to naya message bhi usi ke liye mana jayega,
        # naam lene ki zarurat nahi padegi.
        last = LAST_CHAT.get((m.chat.id, m.from_user.id))
        if last and time.time() - last < 180:
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
        # Baat chal rahi hai, yaad me dal do — taaki agla message
        # bina naam liye bhi Ria samajh jaye ki usi ke liye hai
        LAST_CHAT[(m.chat.id, m.from_user.id)] = time.time()
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
