"""
Real Alert OSINT System - Core Logic
Version: 5.0
Description: Telethon-based client for monitoring, filtering, and validating real-time alerts.
"""

import re
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from dotenv import load_dotenv

# ==========================================
# 1. System Configuration & Mute Telethon Logs
# ==========================================
logging.basicConfig(level=logging.WARNING)
logging.getLogger('telethon').setLevel(logging.WARNING)

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))

CHANNEL_TO_MONITOR = 'tzevaadomm'
USERS_FILE = 'users.json'
VALIDATION_LOG = 'validation.log'
SYSTEM_LOG = 'output.log'

active_prediction = None


# ==========================================
# 2. System Initialization
# ==========================================
def init_system_files():
    """Ensures all required data files exist before the bot starts handling requests."""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    if not os.path.exists(VALIDATION_LOG):
        open(VALIDATION_LOG, 'w', encoding='utf-8').close()
    if not os.path.exists(SYSTEM_LOG):
        open(SYSTEM_LOG, 'w', encoding='utf-8').close()


# ==========================================
# 3. Data & Log Management
# ==========================================
def log_print(message):
    """Custom logging format for the system lifecycle."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def write_validation(status, prediction_score, pre_text, real_text):
    """Appends validation results to the dedicated validation log."""
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
    """Loads the active users list from JSON."""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_user(user_id):
    """Saves a new user to the JSON file if they don't already exist."""
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f)
        return True
    return False


# ==========================================
# 4. Clients Setup
# ==========================================
user_client = TelegramClient('user_session', API_ID, API_HASH)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# ==========================================
# 5. UI Keyboards & Core Logic
# ==========================================
ADMIN_KEYBOARD = [
    [Button.text('📊 סטטוס מערכת', resize=True), Button.text('📢 התראה אחרונה', resize=True)],
    [Button.text('📈 ביצועי מודל', resize=True), Button.text('📋 לוג שרת', resize=True)],
    [Button.request_location('📍 הפעלת התראות (לתושבי האזור)')],
    [Button.text('👥 ניהול משתמשים', resize=True), Button.text('🧹 איפוס לוגים', resize=True)],
    [Button.text('⚙️ חוקי סינון', resize=True)]
]

USER_KEYBOARD = [
    [Button.text('📊 סטטוס מערכת', resize=True), Button.text('📢 התראה אחרונה', resize=True)],
    [Button.request_location('📍 הפעלת התראות (לתושבי האזור)')],
    [Button.text('⚙️ חוקי סינון', resize=True)]
]


def is_in_herzliya_zone(lat, lon):
    """Geo-fencing logic: Returns True if coordinates fall within the defined bounding box."""
    return (32.1527 <= lat <= 32.1807) and (34.8208 <= lon <= 34.8638)


def evaluate_pre_alert(text):
    """Analyzes pre-alert text and returns assessment string and score category."""
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
# 6. Bot Handlers (User & Admin Interface)
# ==========================================
async def show_users_menu(event):
    """Generates the inline keyboard for user management."""
    users = load_users()
    if not users:
        text = "אין משתמשים רשומים במערכת."
        # אם הגענו לכאן בלחיצה על כפתור, נערוך. אם בהודעה, נשלח חדשה.
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(text)
        else:
            await event.reply(text)
        return

    buttons = []
    for uid in users:
        tag = " (אדמין)" if uid == MY_CHAT_ID else ""
        buttons.append([Button.inline(f"❌ הסר את: {uid}{tag}", data=f"del_{uid}".encode('utf-8'))])

    buttons.append([Button.inline("⚠️ מחיקה גורפת", data=b"del_all")])
    text = f"👥 **ניהול רשימת תפוצה**\nסה\"כ מנויים פעילים: {len(users)}\n\nבחר משתמש להסרה:"

    # התיקון הקריטי כאן:
    if isinstance(event, events.CallbackQuery.Event):
        await event.edit(text, buttons=buttons)
    else:
        await event.reply(text, buttons=buttons)


@bot_client.on(events.CallbackQuery)
async def callback_handler(event):
    """Handles clicks on the inline management keyboards."""
    if event.sender_id != MY_CHAT_ID:
        await event.answer("אין הרשאת גישה.", alert=True)
        return

    data = event.data.decode('utf-8')
    users = load_users()

    try:
        if data == 'del_all':
            users = [MY_CHAT_ID]
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f)
            await event.answer("✅ כולם הוסרו בהצלחה (למעט האדמין).", alert=True)
            await show_users_menu(event)

        elif data.startswith('del_'):
            uid_to_del = int(data.split('_')[1])
            if uid_to_del != MY_CHAT_ID:
                users = [u for u in users if u != uid_to_del]
                with open(USERS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(users, f)
                await event.answer(f"✅ משתמש {uid_to_del} הוסר.", alert=True)
                await show_users_menu(event)
            else:
                await event.answer("❌ לא ניתן למחוק את מנהל המערכת.", alert=True)
    except Exception as e:
        log_print(f"Error in callback: {str(e)}")
        await event.answer("❌ אירעה שגיאה בביצוע הפעולה.", alert=True)


@bot_client.on(events.NewMessage)
async def command_center(event):
    """Handles incoming bot commands from users and admins."""
    user_id = event.sender_id

    if user_id == MY_CHAT_ID:
        save_user(user_id)

    # Geo-Location processing
    if event.message.media and hasattr(event.message.media, 'geo'):
        lat, lon = event.message.media.geo.lat, event.message.media.geo.long
        if is_in_herzliya_zone(lat, lon):
            save_user(user_id)
            await event.reply("✅ **אימות מיקום הצליח!** צורפת לרשימת התפוצה לקבלת התראות אמת.")
        else:
            await event.reply("❌ **מחוץ לטווח:** המערכת פתוחה עבורך כסביבת דמו בלבד.")
        return

    command = event.raw_text.strip()
    kb = ADMIN_KEYBOARD if user_id == MY_CHAT_ID else USER_KEYBOARD

    if command in ['/start', 'start', 'עזרה']:
        await event.reply("🤖 **Real Alert System v5.0**\nבחר פעולה מהתפריט:", buttons=kb)

    elif command == '📊 סטטוס מערכת':
        await event.reply("✅ שירותי המערכת פעילים. האזנה שקטה רצה ברקע.", buttons=kb)

    elif command == '📢 התראה אחרונה':
        async for m in user_client.iter_messages(CHANNEL_TO_MONITOR, limit=1):
            await event.reply(f"📢 **הודעה אחרונה מהערוץ:**\n\n{m.text}", buttons=kb)

    elif command == '⚙️ חוקי סינון':
        rules = "📏 **לוגיקת סינון קיימת:**\n1. זיהוי וקטור דן-שרון.\n2. פסילת וקטור צפוני / מזרחי.\n3. מלבן חוסם (Geo-Fencing) כירורגי."
        await event.reply(rules, buttons=kb)

    elif command == '📈 ביצועי מודל' and user_id == MY_CHAT_ID:
        with open(VALIDATION_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            content = "".join(lines[-40:]) if lines else "אין עדיין נתונים לאימות."
        await event.reply(f"📈 **יומן ביצועים (Validation):**\n\n```text\n{content}\n```")

    elif command == '📋 לוג שרת' and user_id == MY_CHAT_ID:
        with open(SYSTEM_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            content = "".join(lines[-30:]) if lines else "הלוג ריק."
        await event.reply(f"📋 **לוג מערכת אחרון:**\n\n```text\n{content}\n```")

    elif command == '👥 ניהול משתמשים' and user_id == MY_CHAT_ID:
        await show_users_menu(event)

    elif command == '🧹 איפוס לוגים' and user_id == MY_CHAT_ID:
        open(SYSTEM_LOG, 'w', encoding='utf-8').close()
        open(VALIDATION_LOG, 'w', encoding='utf-8').close()
        await event.reply("✅ קבצי הלוג ומעקב הביצועים אופסו ל-0 בתים.")


# ==========================================
# 7. OSINT Monitor (Raw Channel Handler)
# ==========================================
@user_client.on(events.NewMessage(chats=CHANNEL_TO_MONITOR))
async def alert_handler(event):
    """Processes incoming messages from the raw alerts channel."""
    global active_prediction
    msg_text = event.message.message
    if not msg_text: return

    short = msg_text[:30].replace('\n', ' ')

    if "התרעה מקדימה" in msg_text:
        assessment, score = evaluate_pre_alert(msg_text)
        if score == "NOT_DAN":
            log_print(f"[{short}...] | רלוונטי: לא | הופץ: לא | סיבה: לא אזור דן")
            return

        active_prediction = {"timestamp": datetime.now(), "text": msg_text, "score": score}
        log_print(f"[{short}...] | רלוונטי: כן | הופץ: כן | פעולה: טיימר הופעל [{score}]")
        await bot_client.send_message(MY_CHAT_ID, f"🔍 **חיזוי פעיל:** {score}")

        if assessment:
            for uid in load_users():
                try:
                    await bot_client.send_message(uid, f"**🤖 ניתוח מערכת:**\n\n{assessment}\n\n**מקור:** {short}...")
                except:
                    pass

    elif "צבע אדום" in msg_text:
        if "הרצליה" in msg_text:
            if active_prediction and (datetime.now() - active_prediction['timestamp']) < timedelta(minutes=15):
                status = "SUCCESS ✅" if active_prediction['score'] == "HIGH" else "PARTIAL SUCCESS ⚠️"
                log_print(f"[{short}...] | רלוונטי: כן | הופץ: כן | סטטוס: {status}")
                write_validation(status, active_prediction['score'], active_prediction['text'], msg_text)
                await bot_client.send_message(MY_CHAT_ID, f"📊 **ביקורת אימות:** {status}")
                active_prediction = None
            else:
                log_print(f"[{short}...] | רלוונטי: כן | הופץ: כן | סטטוס: כישלון מודל ❌")
                write_validation("MISS/FAILURE ❌", "None/Low", "N/A", msg_text)
                await bot_client.send_message(MY_CHAT_ID, "🚨 **כשל אלגוריתם:** אזעקה בהרצליה ללא התרעה מקדימה שנקלטה!")
        else:
            log_print(f"[{short}...] | רלוונטי: לא | הופץ: לא | סיבה: מיקום ירי אחר")

    elif "סיום אירוע" in msg_text:
        log_print(f"[{short}...] | רלוונטי: לא | הופץ: לא | סיבה: הודעת סיום (חזל\"ש)")
    else:
        log_print(f"[{short}...] | רלוונטי: לא | הופץ: לא | סיבה: פורמט חריג / לא מזוהה")


# ==========================================
# 8. Main Entry Point
# ==========================================
async def main():
    init_system_files()
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    log_print("System Online: v5.0 Active. Monitoring targets.")
    await asyncio.gather(user_client.run_until_disconnected(), bot_client.run_until_disconnected())


if __name__ == '__main__':
    asyncio.run(main())