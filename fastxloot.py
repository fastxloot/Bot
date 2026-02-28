import telebot
import requests
import time
import sqlite3
import threading
import re
from telebot import types
from datetime import datetime

# ================= CONFIGURATION =================
BOT_TOKEN = "8435195647:AAFm3NSl8PLOt7c5ww8vGkgBxOklcBF70cw" 
ADMIN_ID = 7518884199
LOG_GROUP_ID = -1003833514650
CHANNEL_USERNAME = "@xpanel576" 
CHANNEL_LINK = "https://t.me/xpanel576"

# 👉 YAHAN APNE BOT KA USERNAME DAALEIN (Bina @ ke) 👈
BOT_USERNAME = "Callback_data_bot" 

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- DATABASE SYSTEM ----------------

def db_exec(query, params=(), fetch=False):
    with sqlite3.connect('stexsms_termux.db', check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()

db_exec('''CREATE TABLE IF NOT EXISTS inventory_v2 
           (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, name TEXT, flag TEXT, range TEXT, service TEXT)''')
db_exec('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')

# ---------------- API ENGINE ----------------

class SMS_API:
    def __init__(self):
        self.session = requests.Session()
        self.email = "dhanniKumar40@gmail.com"
        self.password = "D1H2A3N4@1"
        self.token = None
        self.base_url = "https://x.mnitnetwork.com/mapi/v1" 
        self.ua = 'Mozilla/5.0 (Linux; Android 11; SM-A507FN)'

    def login(self):
        try:
            url = f"{self.base_url}/mauth/login"
            headers = {'User-Agent': self.ua, 'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json'}
            r = self.session.post(url, json={"email": self.email, "password": self.password}, headers=headers, timeout=15).json()
            self.token = r.get('token') or r.get('data', {}).get('token')
            return self.token
        except: return None

    def get_balance(self):
        if not self.token: self.login()
        try:
            url = f"{self.base_url}/mdashboard/user/profile"
            r = self.session.get(url, headers={'mauthtoken': str(self.token)}, timeout=10).json()
            return r.get('data', {}).get('balance', '0.00')
        except: return "Error"

    def buy_3_numbers(self, target_range):
        if not self.token: self.login()
        url = f"{self.base_url}/mdashboard/getnum/number"
        payload = {"range": str(target_range).upper().strip(), "is_national": False, "remove_plus": False}
        nums, error_log = [], ""
        
        headers = {
            'User-Agent': self.ua,
            'Accept': 'application/json, text/plain, */*',
            'mauthtoken': str(self.token),
            'Cookie': f'mauthtoken={self.token}'
        }

        for _ in range(3):
            try:
                res = self.session.post(url, json=payload, headers=headers, timeout=10)
                if res.status_code == 401:
                    self.login()
                    headers['mauthtoken'] = str(self.token)
                    headers['Cookie'] = f'mauthtoken={self.token}'
                    res = self.session.post(url, json=payload, headers=headers, timeout=10)

                if res.status_code == 200:
                    data = res.json()
                    n = data.get('number') or data.get('data', {}).get('number')
                    if n: nums.append(str(n))
                    else: error_log = data.get('message', 'Out of Stock')
                else: error_log = f"HTTP {res.status_code}"
            except Exception as e:
                error_log = "API Timeout"
            time.sleep(0.3) 
            
        return nums, error_log

api = SMS_API()

# ---------------- HELPERS ----------------

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return True

def register_user(user_id):
    db_exec("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))

# ---------------- CORE LOGIC ----------------

def start_purchase(chat_id, rng, service, mid=None):
    if not is_subscribed(chat_id):
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
        bot.send_message(chat_id, "<b>❌ Channel Join Karein!</b>\nJoin @xpanel576 to use this bot.", reply_markup=markup, parse_mode="HTML")
        return

    wait_txt = f"<b>⏳ Requesting Premium Numbers...</b>\nRange: <code>{rng}</code>"
    if mid:
        try: msg = bot.edit_message_text(wait_txt, chat_id, mid, parse_mode="HTML")
        except: msg = bot.send_message(chat_id, wait_txt, parse_mode="HTML")
    else:
        msg = bot.send_message(chat_id, wait_txt, parse_mode="HTML")

    nums, err = api.buy_3_numbers(rng)
    if nums:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for n in nums:
            markup.add(types.InlineKeyboardButton(text=f" {n}", copy_text=types.CopyTextButton(text=str(n))))
        
        markup.row(
            types.InlineKeyboardButton("🔄 Change Number", callback_data=f"chg_{rng}_{service}"),
            types.InlineKeyboardButton("🔙 Menu", callback_data="start")
        )

        premium_msg = (
            f"<b>✅ Premium Numbers Activated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Service:</b> <code>{service}</code>\n"
            f"👇 <i>Tap buttons below to copy numbers</i>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>⏳ Waiting for OTP...</b>"
        )
        bot.edit_message_text(premium_msg, chat_id, msg.message_id, reply_markup=markup, parse_mode="HTML")
        
        threading.Thread(target=otp_monitor_batch, args=(chat_id, nums, service, rng), daemon=True).start()
    else:
        bot.edit_message_text(f"<b>❌ Failed!</b>\nReason: <code>{err}</code>", chat_id, msg.message_id, parse_mode="HTML")

def otp_monitor_batch(chat_id, nums, service, rng):
    start_time = time.time()
    pending_nums = nums.copy()
    
    headers = {
        'User-Agent': api.ua,
        'Accept': 'application/json, text/plain, */*',
        'mauthtoken': str(api.token),
        'Cookie': f'mauthtoken={api.token}'
    }

    s_emoji = {"whatsapp": "💬", "telegram": "✈️", "facebook": "🔵", "google": "🌐"}.get(service.lower(), "💬")

    while pending_nums and (time.time() - start_time < 900): # 15 mins timeout
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"{api.base_url}/mdashboard/getnum/info?date={today}&page=1"
            
            res = requests.get(url, headers=headers, timeout=10).json() 
            
            data_block = res.get('data', [])
            data_list = data_block.get('numbers', []) if isinstance(data_block, dict) else data_block
            if not isinstance(data_list, list): data_list = []
            
            for p_num in pending_nums[:]:
                clean_p = str(p_num).replace("+", "")
                
                for order in data_list:
                    if clean_p in str(order.get('number', '')):
                        m = order.get('otp') or order.get('message') 
                        
                        if m and len(str(m)) > 2:
                            clean_msg = str(m).replace("-", "").replace(" ", "")
                            otp_matches = re.findall(r'\d{4,8}', clean_msg)
                            if not otp_matches: continue 
                            final_otp = otp_matches[0]

                            c_info = db_exec("SELECT name, flag FROM inventory_v2 WHERE ? LIKE code || '%'", (clean_p,), fetch=True)
                            c_name = c_info[0][0] if c_info else "Mixed"
                            c_flag = c_info[0][1] if c_info else "🌍"

                            masked_num = str(p_num)[:4] + "***" + str(p_num)[-3:]

                            # 🔥 TEXT FOR USER (Eagles/Fire Removed)
                            bot_text = f"{c_flag} {s_emoji} <b>{c_name} ⚡ {p_num}⚡     </b>"
                            
                            # 🔥 TEXT FOR GROUP (Eagles/Fire Removed)
                            group_text = f"{c_flag} {s_emoji} <b>{c_name} ⚡ {masked_num}⚡    </b>"
                            
                            # ---------------- GROUP KEYBOARD (Updated Layout) ----------------
                            markup_group = types.InlineKeyboardMarkup()
                            
                            # Button 1 & 2 (Top Row)
                            btn_otp = types.InlineKeyboardButton(text=f" {final_otp}", copy_text=types.CopyTextButton(text=str(final_otp)))
                            btn_msg = types.InlineKeyboardButton(text=f" Full Message", copy_text=types.CopyTextButton(text=str(m)))
                            markup_group.row(btn_otp, btn_msg)
                            
                            # Button 3 (Bottom Row)
                            deep_link_url = f"https://t.me/{BOT_USERNAME}?start=buy_{rng}_{service}"
                            btn_buy = types.InlineKeyboardButton(text=f"🛒 Get Number {rng}", url=deep_link_url)
                            markup_group.row(btn_buy)

                            # ---------------- USER KEYBOARD (Sirf OTP Copy) ----------------
                            markup_user = types.InlineKeyboardMarkup()
                            markup_user.add(types.InlineKeyboardButton(
                                text=f" {final_otp}", 
                                copy_text=types.CopyTextButton(text=str(final_otp))
                            ))

                            # Sending Message
                            try: bot.send_message(chat_id, bot_text, reply_markup=markup_user, parse_mode="HTML")
                            except: pass
                            
                            try: bot.send_message(LOG_GROUP_ID, group_text, reply_markup=markup_group, parse_mode="HTML")
                            except: pass

                            pending_nums.remove(p_num)
                            break 

        except Exception as e:
            pass
        
        time.sleep(8) 

# ---------------- HANDLERS ----------------

@bot.message_handler(commands=['start'])
def welcome(m):
    register_user(m.from_user.id)
    
    # 🔥 DEEP LINKING INTERCEPTOR 🔥
    args = m.text.split()
    if len(args) > 1 and args[1].startswith("buy_"):
        parts = args[1].split("_", 2)
        if len(parts) == 3:
            _, rng, srv = parts
            start_purchase(m.chat.id, rng, srv)
            return

    # Normal Start Menu
    if not is_subscribed(m.from_user.id):
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
        bot.send_message(m.chat.id, "<b>👋 Join @xpanel576 to start!</b>", reply_markup=markup, parse_mode="HTML")
        return
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    services = ["WhatsApp", "Telegram", "Facebook", "Google"]
    markup.add(*[types.InlineKeyboardButton(f"{s}", callback_data=f"srv_{s}") for s in services])
    bot.send_message(m.chat.id, "<b>🚀 MULTI BOT</b>\n<b>Select Service:</b>", reply_markup=markup, parse_mode="HTML")

@bot.message_handler(commands=['buy'])
def buy_cmd(m):
    args = m.text.split()
    if len(args) > 1:
        start_purchase(m.chat.id, args[1], "Direct Buy")
    else:
        bot.reply_to(m, "❌ Usage: /buy 23762003XXX", parse_mode="HTML")

@bot.message_handler(commands=['admin'])
def admin_menu(m):
    if m.from_user.id != ADMIN_ID: return
    bal = api.get_balance()
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌍 Add Country", callback_data="adm_country"),
        types.InlineKeyboardButton("📊 Add Range", callback_data="adm_range"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc")
    )
    bot.send_message(m.chat.id, f"<b>🛠 Admin Panel</b>\n<b>💰 Balance: ${bal}</b>", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: True)
def router(c):
    if c.data.startswith("srv_"):
        srv = c.data.split("_")[1]
        data = db_exec("SELECT code, flag, name FROM inventory_v2 WHERE service COLLATE NOCASE = ?", (srv,), fetch=True)
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(f"{d[1]} {d[2]}", callback_data=f"get_{d[0]}_{srv}") for d in data]
        if buttons: markup.add(*buttons)
        
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="start"))
        bot.edit_message_text(f"<b>🌍 {srv} - Select Country:</b>", c.message.chat.id, c.message.message_id, reply_markup=markup, parse_mode="HTML")
    
    elif c.data.startswith("get_"):
        code, srv = c.data.split("_")[1], c.data.split("_")[2]
        res = db_exec("SELECT range FROM inventory_v2 WHERE code = ? AND service COLLATE NOCASE = ?", (code, srv), fetch=True)
        if res: start_purchase(c.message.chat.id, res[0][0], srv, c.message.message_id)
        
    elif c.data.startswith("chg_"):
        rng, srv = c.data.split("_")[1], c.data.split("_")[2]
        start_purchase(c.message.chat.id, rng, srv, c.message.message_id)

    elif c.data == "start":
        if not is_subscribed(c.from_user.id):
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
            bot.edit_message_text("<b>👋 Join @xpanel576 to start!</b>", c.message.chat.id, c.message.message_id, reply_markup=markup, parse_mode="HTML")
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        services = ["WhatsApp", "Telegram", "Facebook", "Google"]
        markup.add(*[types.InlineKeyboardButton(f"{s}", callback_data=f"srv_{s}") for s in services])
        try:
            bot.edit_message_text("<b>🚀 MULTI BOT</b>\n<b>Select Service:</b>", c.message.chat.id, c.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass 

    elif c.data == "adm_country":
        sent = bot.send_message(c.message.chat.id, "<b>📝 Send: Code | Name | Flag | Service</b>\n<i>Example: 60 | Malaysia | 🇲🇾 | WhatsApp</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, save_country)

    elif c.data == "adm_range":
        sent = bot.send_message(c.message.chat.id, "<b>📝 Send: Code | Range</b>\n<i>Example: 60 | 6017</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, save_range)

    elif c.data == "adm_bc":
        sent = bot.send_message(c.message.chat.id, "<b>📢 Send Broadcast Message:</b>", parse_mode="HTML")
        bot.register_next_step_handler(sent, start_bc)

def save_country(m):
    try:
        c, n, f, s = [i.strip() for i in m.text.split("|")]
        exists = db_exec("SELECT id FROM inventory_v2 WHERE code=? AND service COLLATE NOCASE=?", (c, s), fetch=True)
        if exists:
            db_exec("UPDATE inventory_v2 SET name=?, flag=? WHERE id=?", (n, f, exists[0][0]))
        else:
            db_exec("INSERT INTO inventory_v2 (code, name, flag, range, service) VALUES (?,?,?,?,?)", (c,n,f,"SET_RANGE",s))
        bot.reply_to(m, "<b>✅ Country Added Successfully!</b>", parse_mode="HTML")
    except: bot.reply_to(m, "<b>❌ Format Error. Correct format: Code | Name | Flag | Service</b>\n<i>Note: Use spacing properly!</i>", parse_mode="HTML")

def save_range(m):
    try:
        c, r = [i.strip() for i in m.text.split("|")]
        db_exec("UPDATE inventory_v2 SET range = ? WHERE code = ?", (r, c))
        bot.reply_to(m, "<b>✅ Range Updated Successfully!</b>", parse_mode="HTML")
    except: bot.reply_to(m, "<b>❌ Format Error. Correct format: Code | Range</b>", parse_mode="HTML")

def start_bc(m):
    users = db_exec("SELECT user_id FROM users", fetch=True)
    for u in users:
        try: bot.copy_message(u[0], m.chat.id, m.message_id)
        except: pass
    bot.send_message(m.chat.id, "<b>✅ Done!</b>", parse_mode="HTML")

if __name__ == "__main__":
    print(f"🔥 BOT IS RUNNING - Check line 16 for BOT_USERNAME")
    bot.infinity_polling()
