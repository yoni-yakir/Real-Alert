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
    [Button.request_location('📍 הפעלת התראות (לתושבי האזור)')],
    [Button.text('👥 ניהול משתמשים', resize=True), Button.text('🧹 איפוס לוגים', resize=True)],
    [Button.text('⚙️ חוקי סינון', resize=True)]
]

USER_KEYBOARD = [
    [Button.text('📊 סטטוס מערכת', resize=True), Button.text('📢 התראה אחרונה', resize=True)],
    [Button.request_location('📍 הפעלת התראות (לתושבי האזור)')],
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
# 5. מנוע הניתוח וסינון מיקום
# ==========================================
def is_in_herzliya_zone(lat, lon):
    return (32.1527 <= lat <= 32.1807) and (34.8208 <= lon <= 34.8638)


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

async def show_users_menu(event):
    users = load_users()
    if not users:
        text = "אין משתמשים רשומים במערכת כרגע."
        if hasattr(event, 'edit'):
            await event.edit(text)
        else:
            await event.reply(text)
        return

    buttons = []
    for uid in users:
        label = f"👤 {uid}" + (" (אדמין)" if uid == MY_CHAT_ID else "")
        buttons.append([Button.inline(f"❌ מחק את: {label}", data=f"deluser_{uid}".encode('utf-8'))])

    buttons.append([Button.inline("⚠️ מחיקה גורפת (כל המשתמשים)", data=b"delall_users")])

    text = f"👥 **לוח ניהול משתמשים**\nסה\"כ רשומים במערכת: {len(users)}\n\nבחר משתמש להסרה מרשימת התפוצה:"
    if hasattr(event, 'edit'):
        await event.edit(text, buttons=buttons)
    else:
        await event.reply(text, buttons=buttons)


@bot_client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    if user_id != MY_CHAT_ID:  # הגנת אבטחה: רק האדמין יכול ללחוץ על הכפתורים השקופים
        return

    data = event.data.decode('utf-8')

    if data.startswith('deluser_'):
        target_id = int(data.split('_')[1])
        users = load_users()
        if target_id in users:
            users.remove(target_id)
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f)
            await event.answer(f"משתמש {target_id} נמחק בהצלחה.", alert=True)
            await show_users_menu(event)  # רענון התפריט
        else:
            await event.answer("שגיאה: המשתמש לא נמצא.", alert=True)

    elif data == 'delall_users':
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)
        await event.answer("כל המשתמשים נמחקו מהמערכת.", alert=True)
        await show_users_menu(event)


@bot_client.on(events.NewMessage)
async def command_center(event):
    user_id = event.sender_id

    # הבטחת קבלת התראות לאדמין תמיד
    if user_id == MY_CHAT_ID:
        save_user(user_id)

    # --- אימות מיקום ---
    if event.message.media and hasattr(event.message.media, 'geo'):
        lat = event.message.media.geo.lat
        lon = event.message.media.geo.long
        if is_in_herzliya_zone(lat, lon):
            if save_user(user_id):
                await event.reply("✅ **אימות מיקום הצליח!** צורפת לרשימת התפוצה.")
            else:
                await event.reply("✅ אתה כבר רשום במערכת.")
        else:
            await event.reply("❌ **מחוץ לטווח:** המערכת פתוחה עבורך להתנסות בממשק בלבד.")
        return

    command = event.raw_text.strip()
    keyboard = ADMIN_KEYBOARD if user_id == MY_CHAT_ID else USER_KEYBOARD

    if command in ['/start', 'start', 'עזרה']:
        await event.reply("🤖 **Real Alert v4.3**", buttons=keyboard)

    elif command == '📊 סטטוס מערכת':
        await event.reply("✅ המערכת פעילה ומנטרת.", buttons=keyboard)

    elif command == '📢 התראה אחרונה':
        msg = await event.reply("⏳ שולף...")
        async for message in user_client.iter_messages(CHANNEL_TO_MONITOR, limit=1):
            await msg.edit(f"📢 **הודעה אחרונה:**\n\n{message.text}")

    elif command == '📈 ביצועי מודל' and user_id == MY_CHAT_ID:
        if os.path.exists(VALIDATION_LOG):
            with open(VALIDATION_LOG, 'r', encoding='utf-8') as f:
                content = "".join(f.readlines()[-40:])
                await event.reply(f"📈 **יומן אימות:**\n\n```text\n{content}\n```")
        else:
            await event.reply("יומן הביצועים ריק כרגע.")

    elif command == '📋 לוג שרת' and user_id == MY_CHAT_ID:
        if os.path.exists('output.log'):
            with open('output.log', 'r', encoding='utf-8') as f:
                lines = "".join(f.readlines()[-30:])
                await event.reply(f"📋 **לוג:**\n\n```text\n{lines}\n```")

    elif command == '👥 ניהול משתמשים' and user_id == MY_CHAT_ID:
        await show_users_menu(event)

    elif command == '🧹 איפוס לוגים' and user_id == MY_CHAT_ID:
        try:
            if os.path.exists('output.log'):
                open('output.log', 'w').close()  # מרוקן את הקובץ מבלי למחוק אותו
            if os.path.exists(VALIDATION_LOG):
                open(VALIDATION_LOG, 'w').close()
            await event.reply("✅ הלוגים נוקו בהצלחה. הקבצים אופסו ל-0 בתים.", buttons=keyboard)
        except Exception as e:
            await event.reply(f"❌ שגיאה בניקוי הלוגים: {e}", buttons=keyboard)


@user_client.on(events.NewMessage(chats=CHANNEL_TO_MONITOR))
async def alert_handler(event):
    global active_prediction
    msg_text = event.message.message
    if not msg_text: return

    # --- טיפול בהתרעה מקדימה ---
    if "התרעה מקדימה" in msg_text:
        assessment, score_type = evaluate_pre_alert(msg_text)

        if score_type == "NOT_DAN":
            log_print(f"Pre-Alert Ignored: Not Dan region ({msg_text[:30]}...)", "IGNORED")
            return

        active_prediction = {"timestamp": datetime.now(), "text": msg_text, "score": score_type}
        log_print(f"Prediction Stored: {score_type}", "PREDICT")
        await bot_client.send_message(MY_CHAT_ID, f"🔍 **חיזוי נשמר:** {score_type}")

        if assessment:
            full_msg = f"**🤖 ניתוח OSINT:**\n\n{assessment}\n\n**מקור:**\n{msg_text}"
            for uid in load_users():
                try:
                    await bot_client.send_message(uid, full_msg)
                except:
                    pass

    # --- טיפול בצבע אדום ---
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
                await bot_client.send_message(MY_CHAT_ID, "🚨 **כישלון מודל:** הרצליה ללא חיזוי!")
        else:
            northern_terms = ["קו העימות", "גולן", "הגולן", "גליל", "הגליל", "המפרץ", "כרמל", "הכרמל", "סיום אירוע"]
            if any(term in msg_text for term in northern_terms):
                log_print(f"Red Color Ignored: Northern region/Event end.", "IGNORED")
            else:
                log_print(f"Red Color Ignored: Other region (e.g. Negev/South). Content: {msg_text[:40]}...", "IGNORED")


# ==========================================
# 7. הפעלה
# ==========================================
async def main():
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)
    log_print("🚀 המערכת באוויר! (v4.3 - Admin Dashboard)")
    await asyncio.gather(user_client.run_until_disconnected(), bot_client.run_until_disconnected())


if __name__ == '__main__':
    asyncio.run(main())