# -*- coding: utf-8 -*-
"""
RIA BOT v9 - SIRF CONTENT BOT (/shayari, /joke, /quiz)
======================================================
v9 me bada badlav (Amarjeet ke kehne par):
- Chat/reply wala AI POORA HATA diya. Group me chatting ke liye
  dusre AI bots (Riya, Shreya waghera) jud chuke hain.
- Ria ab BAAT NAHI karti. Wo sirf 3 command par kaam karti hai:
      /shayari  - shayari
      /joke     - joke
      /quiz     - funny paheli (jawab chhupa hua, tap karke dikhega)
- Data kabhi khatm na ho, iske liye:
    1) Pehle AI (OpenRouter) har baar NAYA content banata hai.
    2) AI fail ho ya key na ho, to andar ka bada stock chalta hai -
       aur stock bhi bina repeat ghumta hai (shuffled deck system).
- Balance Game, awaaz, /couple, /spin - sab hataya gaya.
Token code me NAHI hai - Render ke Environment (BOT_TOKEN,
OPENROUTER_API_KEY) se aata hai, pehle jaise hi.
"""

import html
import os
import random
import time
import traceback

import requests
import telebot
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
AI_MODEL = "meta-llama/llama-3.1-8b-instruct:free"

app = Flask(__name__)


def log(*args):
    print(*args, flush=True)


# ============================================================
#  CONTENT MACHINERY - deck (bina repeat) + AI (hamesha naya)
# ============================================================

_decks = {}   # (chat_id, kind) -> bachi hui shuffled list
_recent = {}  # (chat_id, kind) -> aakhri bheji cheezon ki list


def deck_draw(chat_id, kind, pool):
    """Stock se ek item do - poora stock khatm hue bina repeat nahi."""
    key = (chat_id, kind)
    deck = _decks.get(key)
    if not deck:
        deck = list(pool)
        random.shuffle(deck)
        _decks[key] = deck
    item = deck.pop()
    _mark_recent(chat_id, kind, item if isinstance(item, str) else item[0])
    return item


def _mark_recent(chat_id, kind, text):
    key = (chat_id, kind)
    lst = _recent.setdefault(key, [])
    lst.append(" ".join(str(text).lower().split())[:60])
    del lst[:-25]


def _is_recent(chat_id, kind, text):
    key = (chat_id, kind)
    norm = " ".join(str(text).lower().split())[:60]
    return norm in _recent.get(key, [])


THEMES = {
    "shayari": ["mohabbat", "dosti", "baarish", "chai", "neend", "mobile phone",
                "imtihaan", "maa ke haath ka khana", "chand", "hasna", "zindagi",
                "crush", "baarish aur pakode", "sapne", "muskaan"],
    "joke": ["student aur teacher", "pati patni", "do dost", "doctor aur mareez",
             "mobile aur wifi", "exam aur padhai", "naukri aur boss", "bachcha aur maa",
             "train ka safar", "cricket", "khana banana", "neend aur alarm"],
    "quiz": ["jaanwar", "roz ki cheezein", "khana", "school", "safar",
             "mausam", "shareer", "ghar ki cheezein", "waqt", "paani"],
}

PROMPTS = {
    "shayari": (
        "Ek bilkul nayi funny aur halki romantic shayari banao. "
        "Theme: {theme}. Roman Hindi (Hinglish) me, 2 se 4 line ki ho. "
        "Sirf shayari likho - koi intro, koi title, koi extra baat nahi."
    ),
    "joke": (
        "Ek bilkul naya short funny joke sunao. Theme: {theme}. "
        "Roman Hindi (Hinglish) me, 2 se 5 line ka ho, saaf-suthra ho. "
        "Sirf joke likho - koi intro ya extra baat nahi."
    ),
    "quiz": (
        "Ek funny trick paheli banao jiska jawab unexpected aur mazedaar ho. "
        "Theme: {theme}. Roman Hindi (Hinglish) me. "
        "Format bilkul aisa rakho:\nSawaal: <paheli>\nJawab: <jawab>\n"
        "Example:\nSawaal: Kaunsa panchhi hai jo ud nahi sakta?\n"
        "Jawab: Mara hua panchhi. "
        "Sirf yahi do line likho, aur kuch nahi."
    ),
}


def ai_generate(kind):
    """AI se naya content. Shayari/joke -> text, quiz -> (sawaal, jawab).
    Fail ho to None."""
    if not OPENROUTER_API_KEY:
        return None
    theme = random.choice(THEMES[kind])
    prompt = PROMPTS[kind].format(theme=theme)
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system",
                     "content": "Tum ek Telegram bot ke liye content banati ho. "
                                "Jo manga jaye sirf wahi do, extra kuch mat likho."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 1.0,
                "max_tokens": 220,
            },
            timeout=25,
        )
        if r.status_code != 200:
            log("AI fail, status:", r.status_code)
            return None
        text = r.json()["choices"][0]["message"]["content"].strip()
        if not text:
            return None
        if kind == "quiz":
            q, a = _parse_quiz(text)
            if not q or not a:
                return None
            return (q, a)
        return text.strip('"').strip()
    except Exception:
        log("AI ERROR:\n", traceback.format_exc())
        return None


def _parse_quiz(text):
    q, a = "", ""
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("sawaal") or low.startswith("sawal") or low.startswith("question"):
            q = line.split(":", 1)[-1].strip()
        elif low.startswith("jawab") or low.startswith("jawb") or low.startswith("answer"):
            a = line.split(":", 1)[-1].strip()
    return q, a


def get_content(chat_id, kind, pool):
    """Pehle AI (naya), repeat/fail ho to stock (deck)."""
    item = ai_generate(kind)
    if item is not None:
        check = item if isinstance(item, str) else item[0]
        if not _is_recent(chat_id, kind, check):
            _mark_recent(chat_id, kind, check)
            return item
        log("AI ne repeat diya, stock se le rahe hain")
    return deck_draw(chat_id, kind, pool)


# ============================================================
#  STOCK DATA (AI fail ho to ye chalta hai - bina repeat ghumta hai)
# ============================================================

SHAYARI = [
    "Arz kiya hai — dil deewana hai tera,\npar jeb khaali hai mera,\npyaar to full hai jaaneman,\nbas recharge khatm hai mera! 😜",
    "Mohabbat me humne ye kamaal kar diya,\ndil to diya hi tha, neend bhi haar diya,\nwo kehti hai so jao jaldi,\nhumne raat bhar uske reply ka intezaar kar diya! 😍",
    "Chand ko dekha to teri yaad aayi,\nbaarish hui to teri baat aayi,\nkhana khaya to bhi tu yaad aayi,\nlagta hai bhukh bhi tujhse mil kar aayi! 😄",
    "Teri muskaan pe fida hai ye dil,\nteri baaton me chhupa hai ek mahal,\nbas ek guzarish hai tujhse jaan,\nWiFi ka password bata de, yahi hai asal! 😂",
    "Padhai se mera naata purana hai,\nhar saal fail hona mera thikana hai,\nmaa kehti hai beta kuch ban ja,\nmaine kaha — bana hua to hu, sabka hasana mera kaam hai! 😜",
    "Ishq me humne khud ko luta diya,\ndil diya, chain diya, waqt bhi ganwa diya,\naakhir me pata chala sach ye hai,\ncrush ne humein 'bhaiya' bana diya! 😭😂",
    "Zindagi ek safar hai suhana,\nkabhi hasna, kabhi rona purana,\nbas jeb me ho thoda khana,\nto har din lagta hai tyohaar manana! 😊",
    "Uski gali se guzre to dil ne kaha,\nruk ja bande, yahi hai tera jahaan,\npar jaise hi uske papa ne dekha,\ndil ne kaha — bhaag! galat pata bata raha tha makaan! 😂",
    "Chai bina subah adhuri,\nmaa bina ghar adhura,\ndost bina mehfil adhuri,\naur neend bina mera din adhura! 😴",
    "Dil ka dard dil hi jaane,\nhasne wala kya pehchaane,\njo samjhe bin bole baat,\nwahi dost sabse purane! 🤗",
    "Arz kiya hai — aankhon me neend, dil me chain kahan,\nexam sar par hai, padhai ka naam kahan,\nkal se pakka padhunga ye mera waada hai,\npar 'kal' aata hi nahi, ye sawaal kahan! 😅",
    "Teri yaad me hum shayar ban gaye,\nlafzon ke aise khiladi ban gaye,\nlog puchte hain ye dard kahan se aaya,\nhumne kaha — result wale din se aaya! 😂",
    "Dosti ka rishta anmol hota hai,\nhar mushkil me saath khada hota hai,\npaise maango to gaayab hota hai,\npar khana dikhe to sabse pehle aata hai! 😜",
    "Chaand taaron se roshni aati hai,\nphoolon se khushbu aati hai,\npar sacchi khushi tab aati hai,\njab maa ke haath ki roti aati hai! ❤️",
    "Neend se mera pyaar purana,\naankh khule to lage thikana,\nalarm baje to mann kare rona,\nbas 5 minute aur — yahi hai fasana! 😴",
    "Usko dekha to dil ne zor se dhakka,\npyar ka bhoot sar chadh ke nacha,\npass gaya to pata chala,\nwo to uski behen thi — sapna tha kaccha! 😂",
    "Hasna zaroori hai zindagi me,\ngam to aate rahenge har gali me,\njo har haal me muskura de,\nwahi jeeta hai asal khushi me! 😊",
    "Mobile mera sabse saccha dost hai,\naadhi raat ko bhi saath deta hai,\npar jab battery 1% ho jaye,\nto dil ko asli dard deta hai! 📱😭",
    "Arz kiya hai — waqt ne sikha diya sab kuch,\nkoi apna nahi hota matlab ke bina,\nbas ek maa hi hai jo bin bole samjhe,\nbaaki sab sirf matlab ke yaar bina! ❤️",
    "Padhne baitha to neend aayi,\nneend aayi to sapne me topper aaya,\nsapne me bhi usne yahi kaha,\n'bhai, jag ja — paper me yahi aaya!' 😂",
    "Tere bina dil ko chain kahan,\ntere bina neend ki raat kahan,\npar jab tu khane pe bulati hai,\nto bhukh se pehle main wahan! 😜",
    "Ek hasi ke peeche hazaar gam chhupaye,\nphir bhi duniya ko hum hasate aaye,\njo puche kaisa hai haal mera,\n'mast' keh kar hum aage badh jaye! 😊",
    "Baarish ka mausam, garam pakode,\nsaath me dost, aur gappe bade bade,\nzindagi se aur chahiye kya,\nbas jeb me hon thode paise khade! 😄",
    "Dil ne kaha tu hi manzil hai,\ntere bina har khushi mushkil hai,\npar maa ne kaha beta pehle khana kha,\nto dil ne kaha — thali hi asal mehfil hai! 😂",
    "Ishq aur bukhaar me farq sirf itna hai,\nbukhaar dawa se theek ho jata hai,\nishq ka mareez to tab theek hota hai,\njab 'uski' shaadi ka card aa jata hai! 😜",
    "Sapne dekhe the aasmaan chhune ke,\njaaga to late ho gaya college ke liye,\nzindagi ne sikha diya ek hi sach,\nsapne bade rakho, par alarm bhi laga ke! 😅",
    "Teri ek jhalak pe dil haar gaya,\nwaqt ruk sa gaya, jahaan tham gaya,\nphir achanak bijli ka bill yaad aaya,\nsaara romance pal bhar me utar gaya! 😂",
    "Gham chhupane ki kala humse seekho,\nhaste chehre ki ada humse seekho,\nlog kehte hain kitna khush hai ye,\nandar ka toofan chhupana humse seekho! 😊",
    "Dost wo nahi jo bheed me saath ho,\ndost wo hai jo mushkil me haath ho,\nkhane ke time to sab aa jate hain,\nasli dost wo jo bill pe bhi saath ho! 😜",
    "Subah ki chai aur maa ki daant,\ndono bina din ki shuruaat adhuri,\nek garam karti hai jism ko,\nek banati hai insaan ko poori! ❤️",
    "Arz kiya hai — mohabbat me dhokha khaya,\ndil toota, par ek sabak paaya,\nab dil sirf usi ko dunga,\njiske paas charger bhi ho aur khana bhi banaya! 😂",
    "Chhoti si zindagi hai, has ke guzaar de,\ngam ko bhi thoda muskura ke utaar de,\njo aaj hai kal ho na ho,\nhar pal ko khushi se sanwaar de! 😊",
    "Usne kaha 'tum bahut achhe ho',\ndil khushi se jhoom utha,\nphir usne kaha 'bhai jaise ho',\nsaara jhoom ek pal me toot gaya! 😭😂",
    "Khuda se manga tha ek saathi,\njo samjhe mere dil ki baat,\nphir dost mile tum jaise paagal,\nab to hasi rukti nahi din raat! 😄",
    "Neend aati hai to sapne aate hain,\nsapno me aksar apne aate hain,\npar jab sapne me exam hall aata hai,\nto paseene ke saath jaag jaate hain! 😅",
    "Teri baaton me wo jaadu hai,\njo udaas dil ko hasa de,\nbas ek hi kamzori hai teri,\ntu khana khilaye bina jaane na de! 😜",
    "Zamaana badal gaya, log badal gaye,\nrishton ke matlab badal gaye,\nbas ek maa ka pyaar na badla,\nbaaki sab waqt ke saath badal gaye! ❤️",
    "Haso itna ki gam sharma jaye,\nmuskurao itna ki aansu tham jaye,\nzindagi chhoti hai doston,\nise haste-haste guzaar do, kal jo aaye! 😊",
    "Dil karta hai duniya ghoom aau,\nhar sheher ka khana chakh aau,\npar jeb kehti hai ruk ja bande,\nghar baith, maa ke haath ka kha aau! 😂",
    "Arz kiya hai — uski yaad me raat guzri,\nneend na aayi, bas karwat badli,\nsubah pata chala wajah kuch aur thi,\nkamre me machchar ne party kar li! 🦟😂",
]

JOKES = [
    "Teacher: Batao, bada hokar kya banoge?\nStudent: Sir, bada hokar main ameer banunga.\nTeacher: Wo to sab banna chahte hain, padhoge kaise?\nStudent: Sir, aap tension mat lo — sapne me sab ho gaya hai! 😂",
    "Doctor: Tumhe roz subah jaldi uthna chahiye.\nMareez: Doctor sahab, main to roz jaldi uthta hu.\nDoctor: Phir dikkat kya hai?\nMareez: Uth to jata hu, par phir so jata hu! 😴😂",
    "Pappu: Papa, aaj school nahi jaunga.\nPapa: Kyun beta?\nPappu: Kal teacher ne kaha tha — jo sawal ka jawab nahi dega use khada rakhungi.\nPapa: To?\nPappu: Aaj bhi mujhe jawab nahi aata, pair dard karenge! 😂",
    "Biwi: Suno ji, main kaisi lag rahi hu?\nPati: Ekdum chaand jaisi.\nBiwi: Sach me? 🥰\nPati: Haan... door se hi achhi lagti ho, paas jana mushkil hai! 😂\n(Bhaagne ki awaz)",
    "Teacher: Golu, 'kal' ka sentence banao.\nGolu: Main kal se pakka padhunga.\nTeacher: Ye 'kal' kab aayega?\nGolu: Wahi to madam, 5 saal se yehi sentence bana raha hu! 😅",
    "Ek dost dusre se: Yaar, meri biwi khana bahut achha banati hai.\nDusra: Phir tu udaas kyun hai?\nPehla: Kyunki wo sirf tab banati hai jab uski maa aati hai! 😂",
    "Maa: Beta, doodh pee le, bada ho jayega.\nBeta: Maa, doodh peene se koi bada nahi hota.\nMaa: Kaise pata?\nBeta: Bhains roz peeti hai... matlab ghaas khati hai, phir bhi waisi ki waisi! 😜",
    "Boss: Tum hamesha late kyun aate ho?\nEmployee: Sir, traffic bahut hota hai.\nBoss: Kal se jaldi nikla karo.\nEmployee: Sir, jaldi nikalta hu to traffic me aapki gaadi ke peeche hota hu — aap bhi to late aate ho! 😂",
    "Pappu doctor se: Doctor sahab, mujhe bhoolne ki bimari hai.\nDoctor: Kab se hai ye bimari?\nPappu: Kaunsi bimari? 😂",
    "Teacher: Chintu, agar tumhare paas 10 aam hon aur tumne 3 dost ko de diye to kitne bache?\nChintu: 10 hi bache madam.\nTeacher: Kaise?!\nChintu: Mere dost khali haath aaye the, maine mana kar diya! 😂",
    "Biwi: Shaadi se pehle tum kehte the main tumhare liye chaand taare tod launga.\nPati: Haan, par tab mujhe nahi pata tha ki tum khana banana bhi mujhse hi karwaogi! 😂",
    "Student: Sir, wo kaam ki saza nahi milni chahiye jo maine kiya hi nahi.\nTeacher: Bilkul sahi, beta.\nStudent: To sir, maine homework nahi kiya! 😂",
    "Ek aadmi: Bhai sahab, ye sadak kahan jati hai?\nDusra: Ye sadak kahin nahi jati, yahi padi rehti hai — jana to aapko padega! 😂",
    "Maa: Beta, jaakar sabzi le aa.\nBeta: Maa, bahar bahut garmi hai.\nMaa: To chhata le ja.\nBeta: Maa, sabzi wale ke paas chhata kya karega, wo to dukaan ke andar hai! 😜",
    "Teacher: Ramu, agar main tumhe 2 billi du aur phir 2 aur du, to kul kitni billi hui?\nRamu: 6 madam.\nTeacher: Galat! 4 hoti hain.\nRamu: Madam, mere paas ghar me pehle se 2 hain! 😂",
    "Dost 1: Yaar, kal raat maine sapna dekha ki main raja ban gaya.\nDost 2: Aur main mantri!\nDost 1: Tum mantri kaise?\nDost 2: Kyunki sapna mera tha, posting main hi dunga! 😂",
    "Pati: Aaj khana bahut tasty hai, kya daala hai?\nBiwi: Pyaar.\nPati: Tabhi to pet me jalan ho rahi hai — pyaar hazam nahi hota! 😂",
    "Chintu: Papa, mujhe cycle chahiye.\nPapa: Beta, pehle acche number lao.\nChintu: Papa, cycle mil jaye to number lane school jaldi pahuncha karunga! 😂",
    "Teacher: Batao bachon, bijli kahan se aati hai?\nGolu: Madam, bijli bill se aati hai.\nTeacher: Kaise?\nGolu: Bill na bharo to chali jati hai! 😂",
    "Ek kanjoos dost se: Yaar, tum itne kanjoos kyun ho?\nKanjoos: Kanjoos nahi hu, bachat karta hu.\nDost: Kal tumne khana kyu nahi khaya?\nKanjoos: Kal ka khana aaj ke liye bacha raha tha! 😂",
    "Doctor: Aapko aaram ki sakht zarurat hai.\nMareez: Doctor sahab, main to pura din aaram hi karta hu.\nDoctor: To phir dikkat kya hai?\nMareez: Wahi to — aaram karte karte thak gaya hu! 😂",
    "Biwi: Aji sunte ho, padosan keh rahi thi ki uska pati use roz ghumane le jata hai.\nPati: To tum bhi padosan ke pati ke saath chali jaya karo, mujhe cricket dekhna hota hai! 😂\n(Fir pati 2 din se gayab hai)",
    "Teacher: Sonu, tum itne udaas kyun ho?\nSonu: Madam, mere paas pen nahi hai.\nTeacher: To dost se le lo.\nSonu: Madam, dost ke paas bhi nahi hai — hum dono isi liye udaas hain! 😂",
    "Pappu: Maa, main bada hokar pilot banunga.\nMaa: Bahut badhiya beta!\nPappu: Par maa, mujhe unchai se dar lagta hai.\nMaa: To kya banoge?\nPappu: Bus driver — zameen par hi rahunga! 😂",
    "Ek dost: Yaar, meri ghadi band ho gayi.\nDusra: To nayi le le.\nPehla: Nayi lene ka time kahan hai, ghadi band hai isliye time hi nahi dikh raha! 😂",
    "Master ji: Kallu, tum class me sote kyun ho?\nKallu: Master ji, aap padhate hi itne achhe se ho ki neend aa jati hai — bilkul lori jaisa! 😂",
    "Biwi: Main mayke ja rahi hu, 10 din ke liye.\nPati: Theek hai, jao.\nBiwi: Kuch kahoge nahi?\nPati: Bas yahi — 10 din aur badha lo, mausam achha hai wahan! 😂",
    "Chintu doctor se: Doctor sahab, jab main chai peeta hu to aankh me dard hota hai.\nDoctor: Agli baar chai me se chammach nikaal lena! 😂",
    "Teacher: Golu, homework kyun nahi kiya?\nGolu: Madam, bijli chali gayi thi.\nTeacher: To mombatti jala lete.\nGolu: Madam, mombatti thi hi nahi.\nTeacher: Kyun?\nGolu: Bijli jaane se dikhi hi nahi! 😂",
    "Pita: Beta, result kaisa raha?\nBeta: Papa, class me first aaya hu!\nPita: Sach me?! Kis cheez me?\nBeta: Der se aane me! 😂",
    "Ek aadmi train me: Bhai sahab, ye train time par hai?\nDusra: Train to time par hai, bas ghadi 2 ghante peeche chal rahi hai humari! 😂",
    "Maa: Beta, itni der tak phone kyun chalata hai?\nBeta: Maa, main padhai kar raha tha phone par.\nMaa: To itna has kyun raha tha?\nBeta: Maa, padhai me maza aa raha tha! 😂",
    "Dost 1: Yaar, tum roz gym jaate ho, body bani?\nDost 2: Body to nahi bani, par gym wale se dosti pakki ho gayi — ab wo mujhe dekh kar has deta hai! 😂",
    "Teacher: Bachon, mehnat ka phal meetha hota hai.\nPappu: Madam, jhooth! Kal maine ped par chadh kar aam toda, phir bhi kachcha tha! 😂",
    "Pati: Aaj office me boss ne meri bahut taarif ki.\nBiwi: Achha? Kya kaha?\nPati: Kaha — 'tum jaisa kaamchor maine aaj tak nahi dekha, tum ekdum unique ho!' 😂",
    "Chhota bachcha: Maa, mujhe bhookh lagi hai.\nMaa: Abhi khana ban raha hai, 10 minute ruko.\nBachcha: Maa, bhookh ko bol du 10 minute ruk jaye? Wo sunti kahan hai! 😂",
    "Ek kanjoos ne dost ko khana khilaya.\nDost: Yaar, khana to bahut tha, par pet nahi bhara.\nKanjoos: Pet bharna tha to ghar se kha kar aana tha, yahan to sirf dikhawa tha! 😂",
    "Teacher: Ramu, sach bolo — ye homework tumne khud kiya hai?\nRamu: Nahi madam, papa ne kiya hai.\nTeacher: Papa ko bolo aisa na karein.\nRamu: Madam, papa keh rahe the — agli baar wo aur achha karenge, is baar unhe bhi nahi aata tha! 😂",
    "Biwi: Suno, kal tum neend me mera naam le rahe the.\nPati: Sach me? Kya bol raha tha?\nBiwi: Bol rahe the — 'bas karo, aur khana mat do!' 😂",
    "Golu: Sir, mujhe school se chhutti chahiye.\nTeacher: Kyun?\nGolu: Sir, ghar me function hai.\nTeacher: Kaisa function?\nGolu: Sir, maa ne kaha hai — 'aaj tu ghar par reh, bahut kaam hai!' 😂",
    "Ek dost dusre se: Bhai, udhaar de de 500 rupaye.\nDusra: Yaar, mere paas to khud nahi hain.\nPehla: Tu jhooth bol raha hai!\nDusra: Agar hote to main khud tujhse maang raha hota! 😂",
    "Doctor: Tumhe meetha kam karna hoga.\nMareez: Doctor sahab, meetha to main khata hi nahi.\nDoctor: To wazan kaise badha?\nMareez: Sir, meetha khata nahi hu... peeta hu, chai me 4 chammach! 😂",
    "Teacher: Chintu, tumhare paas 5 rupaye hain aur tumne dost ko 2 de diye, kitne bache?\nChintu: 5 madam.\nTeacher: Galat!\nChintu: Madam, aap mere dost ko nahi jaanti — wo lene aayega hi nahi, use pata hai main dunga nahi! 😂",
    "Pappu: Papa, aap kehte ho jhooth bolna buri baat hai.\nPapa: Bilkul beta.\nPappu: To jab maa puchegi ki mithai kisne khayi, main sach bol dunga — aapne! 😂",
]


QUIZ = [
    ("Kaunsa panchhi hai jo ud nahi sakta?", "Mara hua panchhi! 😂"),
    ("Wo kya hai jo tumhara hai, lekin istemal sabse zyada dusre log karte hain?", "Tumhara naam! 😄"),
    ("Wo kya hai jo hamesha aata hai lekin kabhi pahunchta nahi?", "Kal (tomorrow) — wo kabhi aaj nahi banta! 😜"),
    ("Wo kya hai jo jitna zyada nikaalo, utna hi bada hota jata hai?", "Gaddha! Jitni mitti nikaalo, utna bada 😂"),
    ("Bina pankh ke udta hai, bina aankhon ke rota hai — kya hai?", "Baadal! ☁️"),
    ("Kaun se mahine me 28 din hote hain?", "Saare mahino me! Kuch me 28 se zyada bhi hote hain 😂"),
    ("Wo kya hai jo sirf upar jata hai, kabhi neeche nahi aata?", "Tumhari umar! 🎂"),
    ("Ek aadmi bina parachute ke plane se kud gaya, fir bhi zinda bach gaya — kaise?", "Plane zameen par khada tha! 😂"),
    ("Wo kya hai jo dusron ko sukhata hai aur khud geela ho jata hai?", "Tauliya (towel)! 😄"),
    ("Wo kya hai jo tod sakte ho bina haath lagaye?", "Vaada (promise)! Todna sabse aasan kaam hai 😜"),
    ("Wo kya hai jo khana khilane par zinda rehta hai aur paani pilane par mar jata hai?", "Aag! 🔥"),
    ("Kis ke paas gardan hai lekin sir nahi hai?", "Botal ke paas! 🍾"),
    ("Wo kya hai jo ek jagah khada rehta hai, fir bhi poori duniya ghoom aata hai?", "Daak ticket (postage stamp)! ✉️"),
    ("Kis cheez ko dekhne ke liye aankhein band karni padti hain?", "Sapna! 😴"),
    ("Ek kilo rooi aur ek kilo loha — kaunsa zyada bhaari hai?", "Dono barabar! Dono ek-ek kilo hain 😂"),
    ("Wo kya hai jo bolte hi toot jata hai?", "Khamoshi (silence)! 🤫"),
    ("Kis ke paas aankhein hain lekin wo dekh nahi sakta?", "Aloo ke paas! 🥔😂"),
    ("Kis ke daant hain lekin wo kaat nahi sakta?", "Kanghi (comb) ke paas! 😄"),
    ("Ek aadmi tez baarish me bina chhate ke bheeg raha tha, par uske baal nahi bheege — kyun?", "Kyunki wo ganja tha! 😂"),
    ("Kaunsi cheez kaatne par log khushi se taali bajate hain?", "Birthday cake! 🎂"),
    ("Wo kya hai jo hamesha tumhare peeche rehta hai, par tum use pakad nahi sakte?", "Tumhara saaya (shadow)! 🌤️"),
    ("Kaun sa phal hai jo bazaar se khareeda nahi ja sakta?", "Sabr ka phal — wo sirf milta hai, bikta nahi! 😊"),
    ("Ek table par 3 santre rakhe hain. Tumne 2 utha liye. Ab tumhare paas kitne santre hain?", "2 hi — jo uthaye wahi tumhare hain! 😂"),
    ("Wo kya hai jo khareedte samay kaala, istemal karte samay laal aur fekte samay safed hota hai?", "Koyla (coal)! 🔥"),
    ("Aisi kaunsi jagah hai jahan sadak hai par gaadi nahi, jungle hai par ped nahi, sheher hai par ghar nahi?", "Naksha (map)! 🗺️"),
    ("Wo kya hai jo bina pairon ke chalta hai aur bina munh ke bolta hai?", "Hawa! 🌬️"),
    ("Kaunsi cheez daud sakti hai par chal nahi sakti?", "Paani! Nadi ka paani hamesha daudta hai 🌊"),
    ("Kaunsi cheez tumhare saamne hoti hai, par tum use dekh nahi sakte?", "Tumhari naak! 👃😂"),
    ("Ek ladka khidki se gira, fir bhi use chot nahi lagi — kaise?", "Wo sapna dekh raha tha! 😴😂"),
    ("Wo kya hai jo paani me girne par bhi geela nahi hota?", "Tel (oil)! Paani ke upar tairta hai 😄"),
    ("Kis ke paas bahut saari chaabiyan (keys) hain, par wo ek bhi taala nahi khol sakta?", "Keyboard ke paas! ⌨️😂"),
    ("Wo kya hai jo tum jitna baantoge utna badhega?", "Khushi aur gyaan! 😊 (aur group ka khana bhi 😜)"),
    ("Kaunsi cheez sone (gold) se mehngi hai, par sabke paas muft me hai?", "Waqt! ⏰"),
    ("Ek haathi ko fridge me rakhne me kitne step lagte hain?", "3 step — darwaza kholo, haathi rakho, darwaza band karo! 🐘😂"),
    ("To phir jiraaf ko fridge me rakhne me kitne step lagenge?", "4 step — darwaza kholo, haathi nikalo, jiraaf rakho, darwaza band! 🦒😂"),
    ("Wo kya hai jo har roz aata hai, par tum use rok nahi sakte, pakad nahi sakte?", "Naya din / waqt! ⏰"),
    ("Kis cheez ka munh hai par wo kha nahi sakti, bistar hai par so nahi sakti?", "Nadi (river) — uska munh (muhana) bhi hota hai aur bistar (tal) bhi! 🌊"),
    ("Wo kya hai jo chhota sa hai par poora kamra roshan kar deta hai?", "Balb (bulb)! 💡"),
    ("Kaun hai jo bina bole tumhari har baat sun leta hai aur turant jawab bhi deta hai?", "Goonj (echo)! 🗣️"),
    ("Wo kya hai jo aage badhta hai par peeche kabhi nahi hat sakta?", "Waqt! ⏳"),
    ("Ek aadmi 10 din bina soye kaise reh sakta hai?", "Kyunki wo raat ko sota hai! 😂"),
    ("Kaunsi cheez garam karne par jam jati hai?", "Anda (egg)! 🥚😄"),
    ("Wo kya hai jo tumhare paas hai to sabko dikhta hai, nahi hai to koi nahi puchta?", "Muskaan! 😊 Hamesha rakho!"),
    ("Kis ke paas sheher hain par ghar nahi, nadiyan hain par paani nahi?", "Phir se naksha (map) nahi — is baar jawab hai Globe! 🌍😜"),
]

HELP_TEXT = (
    "Main hu <b>Ria</b> 💬\n"
    "Main ab baat-cheet nahi karti — group me chatting ke liye dusre bots hain.\n"
    "Main sirf ye 3 cheezein deti hu, jab command doge tabhi:\n\n"
    "/shayari — nayi shayari 💌\n"
    "/joke — naya joke 😂\n"
    "/quiz — funny paheli (jawab chhupa hua milega) ❓\n\n"
    "Har baar kuch naya milega! ✨"
)

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    log("WARNING: BOT_TOKEN nahi mila. Render > Environment me BOT_TOKEN dalo.")

    @app.route("/")
    def home_no_token():
        return "Ria Bot: BOT_TOKEN missing hai. Render Environment me dalo."
else:
    bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

    try:
        bot.set_my_commands([
            telebot.types.BotCommand("shayari", "Nayi shayari sunao"),
            telebot.types.BotCommand("joke", "Naya joke sunao"),
            telebot.types.BotCommand("quiz", "Funny paheli pucho"),
        ])
    except Exception:
        log("set_my_commands fail:\n", traceback.format_exc())

    @bot.message_handler(commands=["start", "help"])
    def cmd_help(m):
        bot.reply_to(m, HELP_TEXT, parse_mode="HTML")

    @bot.message_handler(commands=["shayari", "sharayi"])
    def cmd_shayari(m):
        item = get_content(m.chat.id, "shayari", SHAYARI)
        bot.reply_to(m, "💌 " + item)

    @bot.message_handler(commands=["joke", "jokes"])
    def cmd_joke(m):
        item = get_content(m.chat.id, "joke", JOKES)
        bot.reply_to(m, "😂 " + item)

    @bot.message_handler(commands=["quiz", "quize"])
    def cmd_quiz(m):
        q, a = get_content(m.chat.id, "quiz", QUIZ)
        text = (
            "❓ <b>Quiz Time!</b>\n\n" + html.escape(q) +
            "\n\n👇 <i>Jawab chhupa hai — dekhne ke liye neeche tap karo</i>\n"
            "<span class=\"tg-spoiler\">" + html.escape(a) + "</span>"
        )
        bot.reply_to(m, text, parse_mode="HTML")

    # ========================================================
    #  WEBHOOK ROUTES (v8 wala mazboot pattern)
    # ========================================================
    @app.route("/")
    def home():
        return "Ria Bot v9 chal raha hai (sirf /shayari /joke /quiz)."

    @app.route("/" + BOT_TOKEN, methods=["POST"])
    def webhook():
        raw = request.get_data(as_text=True)
        try:
            if not raw:
                log("WEBHOOK: khaali body aayi")
                return "ok", 200
            update = telebot.types.Update.de_json(raw)
            if update is None:
                log("WEBHOOK: JSON nahi mila, raw lamba hai:", len(raw or ""))
                return "ok", 200
            log(
                "WEBHOOK: update aaya, id:", update.update_id,
                "| message hai:", bool(update.message),
                "| text:", (update.message.text[:40] if update.message and update.message.text else None),
            )
            bot.process_new_updates([update])
            log("WEBHOOK: process ho gaya, 200 bhej rahe hain")
            return "ok", 200
        except Exception:
            log("WEBHOOK ERROR: kuch gadbad hui, poora error neeche hai")
            log(traceback.format_exc())
            return "ok", 200

    def set_webhook():
        try:
            if not RENDER_EXTERNAL_URL:
                log("RENDER_EXTERNAL_URL nahi mila - webhook abhi set nahi kiya")
                return
            url = RENDER_EXTERNAL_URL.rstrip("/") + "/" + BOT_TOKEN
            bot.remove_webhook()
            time.sleep(1)
            ok = bot.set_webhook(url=url)
            info = bot.get_webhook_info()
            log("WEBHOOK SET:", ok, "| url:", info.url, "| pending:", info.pending_update_count)
        except Exception:
            log("WEBHOOK SET ERROR:\n", traceback.format_exc())

    set_webhook()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
