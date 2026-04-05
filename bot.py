import re
import json
import os
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from dotenv import load_dotenv

# ==========================================
# 1. הגדרות המערכת
# ==========================================
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
CHANNEL_TO_MONITOR = 'tzevaadomm'
USERS_FILE = 'users.json'
VALIDATION_LOG = 'validation.log'

active_prediction = None

# ==========================================
# 2. ממשק משתמש (UI Keyboards)
# ==========================================
ADMIN_KEYBOARD = [
    [Button.text('📊 סטטוס מערכת', resize=True), Button.text('📢 התראה אחרונה', resize=True)],
    [Button.text('📈 ביצועי מודל', resize=True), Button.text('📋 לוג שרת', resize=True)],
    [Button.text('⚙️ חוקי סינון', resize=True)]
]

USER_KEYBOARD = [
    [Button.text('📊 סטטוס מערכת', resize=True), Button.text('📢 התראה אחרונה', resize=True)],
    [Button.text('⚙️ חוקי סינון', resize=True)]
]


# ==========================================
# 3. ניהול נתונים ולוגים
# ==========================================
def log_print(message, tag="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{tag}] {message}")


def write_validation(status, prediction_score, pre_text, real_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"--- {status} ---\n"
        f"זמן: {timestamp}\n"
        f"חיזוי מקורי: {prediction_score}\n"
        f"טקסט מקדים: {pre_text[:100]}...\n"
        f"התראה בפועל: {real_text[:100]}...\n"
        f"{'-' * 30}\n"
    )
    with open(VALIDATION_LOG, 'a', encoding='utf-8') as f:
        f.write(entry)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
        return True
    return False


# ==========================================
# 4. לקוחות
# ==========================================
user_client = TelegramClient('user_session', API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)


# ==========================================
# 5. מנוע הניתוח
# ==========================================
def evaluate_pre_alert(text):
    if "דן" not in text:
        return None, "NOT_DAN"

    has_eastern = any(region in text for region in ["ירושלים", "ים המלח", "ערבה", "דרום הנגב"])
    has_sharon = "שרון" in text
    match = re.search(r'באזורים(.*?)(?:לרשימת|$)', text, re.DOTALL)
    regions_count = len([r for r in match.group(1).split(',') if r.strip()]) if match else text.count(',') + 1

    if not has_sharon:
        return "🟢 **סבירות נמוכה:** דן ללא שרון.", "LOW"
    if has_eastern:
        return "🟡 **סבירות בינונית-נמוכה:** וקטור מזרחי/דרומי.", "MED_LOW"
    if regions_count >= 14:
        return "🟡 **סבירות בינונית:** התרעה רחבה מאוד.", "MED"

    return "🔴 **כוננות שיא להרצליה!** 🔴\nהתרעה ממוקדת דן+שרון.", "HIGH"


# ==========================================
# 6. מאזינים ומרכז פקודות
# ==========================================
@bot_client.on(events.NewMessage)
async def command_center(event):
    user_id = event.sender_id
    command = event.raw_text.strip()
    save_user(user_id)

    keyboard = ADMIN_KEYBOARD if user_id == MY_CHAT_ID else USER_KEYBOARD

    if command in ['/start', 'start', 'עזרה']:
        await event.reply("🤖 **מערכת OSINT הרצליה v4.0**\nבחר פעולה מהתפריט:", buttons=keyboard)

    elif command == '📊 סטטוס מערכת':
        await event.reply("✅ המערכת פעילה. מנוע הסינון וה-Validation רצים ברקע.", buttons=keyboard)

    elif command == '⚙️ חוקי סינון':
        rules = "📏 **חוקי המערכת:**\n1. חיפוש אזור דן והשרון.\n2. סינון אזורי צפון ווקטורים מזרחיים.\n3. אימות מול אזעקות בפועל להרצליה."
        await event.reply(rules, buttons=keyboard)

    elif command == '📢 התראה אחרונה':
        msg = await event.reply("⏳ שולף הודעה אחרונה מהשטח...")
        async for message in user_client.iter_messages(CHANNEL_TO_MONITOR, limit=1):
            await msg.edit(f"📢 **הודעה אחרונה מהערוץ:**\n\n{message.text}")

    elif command == '📈 ביצועי מודל' and user_id == MY_CHAT_ID:
        if os.path.exists(VALIDATION_LOG):
            with open(VALIDATION_LOG, 'r', encoding='utf-8') as f:
                content = "".join(f.readlines()[-40:])
                await event.reply(f"📈 **יומן אימות (Validation):**\n\n```text\n{content}\n```", buttons=keyboard)
        else:
            await event.reply("יומן הביצועים עדיין ריק.", buttons=keyboard)

    elif command == '📋 לוג שרת' and user_id == MY_CHAT_ID:
        if os.path.exists('output.log'):
            with open('output.log', 'r', encoding='utf-8') as f:
                lines = "".join(f.readlines()[-30:])
                await event.reply(f"📋 **30 שורות אחרונות:**\n\n```text\n{lines}\n```", buttons=keyboard)


@user_client.on(events.NewMessage(chats=CHANNEL_TO_MONITOR))
async def alert_handler(event):
    global active_prediction
    msg_text = event.message.message
    if not msg_text: return

    if "התרעה מקדימה" in msg_text:
        assessment, score_type = evaluate_pre_alert(msg_text)
        if score_type == "NOT_DAN": return

        active_prediction = {
            "timestamp": datetime.now(),
            "text": msg_text,
            "score": score_type
        }
        log_print(f"Prediction Stored: {score_type}")
        await bot_client.send_message(MY_CHAT_ID, f"🔍 **חיזוי נשמר:** {score_type}")

        if assessment:
            full_msg = f"**🤖 ניתוח OSINT:**\n\n{assessment}\n\n**מקור:**\n{msg_text}"
            for uid in load_users():
                try:
                    await bot_client.send_message(uid, full_msg)
                except:
                    pass

    elif "צבע אדום" in msg_text:
        is_herzliya = "הרצליה" in msg_text

        if is_herzliya:
            if active_prediction and (datetime.now() - active_prediction['timestamp']) < timedelta(minutes=15):
                status = "SUCCESS ✅" if active_prediction['score'] == "HIGH" else "PARTIAL SUCCESS ⚠️"
                write_validation(status, active_prediction['score'], active_prediction['text'], msg_text)
                await bot_client.send_message(MY_CHAT_ID, f"📊 **ביקורת מודל:** {status}")
                active_prediction = None
            else:
                write_validation("MISS/FAILURE ❌", "None/Low", "N/A", msg_text)
                await bot_client.send_message(MY_CHAT_ID, "🚨 **כישלון מודל:** הרצליה הופעלה ללא התרעה מקדימה מתאימה!")
        else:
            northern_terms = ["קו העימות", "גולן", "הגולן", "גליל", "הגליל", "המפרץ", "כרמל", "הכרמל", "סיום אירוע"]
            if any(term in msg_text for term in northern_terms):
                log_print("Noise Filter: התעלמות מהודעה לא רלוונטית (צפון/סיום).", "IGNORED")
                return


# ==========================================
# 7. הפעלה
# ==========================================
async def main():
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    log_print("🚀 המערכת המלאה באוויר! (v4.0)")
    await asyncio.gather(user_client.run_until_disconnected(), bot_client.run_until_disconnected())


if __name__ == '__main__':
    asyncio.run(main())