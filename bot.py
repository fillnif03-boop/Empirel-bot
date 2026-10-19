import sqlite3, random, time, telebot, threading
from telebot import types
from flask import Flask

TOKEN = "8629585189:AAG2fqhVluKxP5oO64JXrlpHCi-bJFOs8hc"  # <--- ВСТАВЬ СВОЙ ТОКЕН СЮДА
bot = telebot.TeleBot(TOKEN, threaded=True)

# --- ЗАГЛУШКА ДЛЯ RENDER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- БАЗА ДАННЫХ ---
def db_execute(query, params=(), fetch=False):
    conn = sqlite3.connect("game.db")
    cur = conn.cursor()
    cur.execute(query, params)
    res = cur.fetchall() if fetch else None
    if not fetch: conn.commit()
    conn.close()
    return res

db_execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY, username TEXT, empire TEXT,
    coins INTEGER DEFAULT 150, food INTEGER DEFAULT 150, metal INTEGER DEFAULT 150,
    infantry INTEGER DEFAULT 0, artillery INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, territories INTEGER DEFAULT 1,
    army_level INTEGER DEFAULT 1, last_collect INTEGER DEFAULT 0, hero TEXT DEFAULT '',
    last_daily INTEGER DEFAULT 0, fortifications INTEGER DEFAULT 0,
    village INTEGER DEFAULT 0, factory INTEGER DEFAULT 0, shop INTEGER DEFAULT 0,
    tutorial INTEGER DEFAULT 0, regions TEXT DEFAULT '', occupied_by INTEGER DEFAULT 0
)""")

for col in ["village", "factory", "shop", "tutorial", "occupied_by"]:
    try: db_execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
    except: pass
try: db_execute("ALTER TABLE users ADD COLUMN regions TEXT DEFAULT ''")
except: pass

EMPIRES = {
    "🇬🇧 Британская": "Доход +20%", "🇫🇷 Французская": "Атака +15%", "🇩🇪 Германская": "Атака +15%",
    "🇷🇺 Российская": "Армия +15%", "🇦🇹 Австро-Венгрия": "Защита +15%", "🇹🇷 Османская": "Защита +15%",
    "🇯🇵 Японская": "Армия +20%", "🇺🇸 Американская": "Доход +20%", "🇮🇹 Итальянская": "Атака +15%",
    "🇨🇳 Цинская": "Доход +15%"
}

REGIONS = {
    "🌾 Поля": {"bonus": "food", "amount": 10, "cost": 3},
    "⛰ Горы": {"bonus": "metal", "amount": 10, "cost": 4},
    "🏙 Город": {"bonus": "coins", "amount": 15, "cost": 5}
}

def get_user(uid): 
    r = db_execute("SELECT * FROM users WHERE user_id=?", (uid,), fetch=True)
    return r[0] if r else None

def register_user(uid, name):
    if not get_user(uid): db_execute("INSERT INTO users(user_id, username) VALUES(?,?)", (uid, name))

def active_players():
    r = db_execute("SELECT user_id FROM users WHERE empire IS NOT NULL", fetch=True)
    return [x[0] for x in r] if r else []

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏛 Империя", "📊 Статистика", "⚔️ Армия")
    kb.row("💰 Экономика", "🏗 Постройки", "🗺 Карта")
    kb.row("🎖 Генералы", "🔥 Война", "🌍 Арена")
    return kb

def empires_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for n in EMPIRES: kb.add(types.InlineKeyboardButton(n, callback_data=f"emp_{n}"))
    return kb

# --- СТАРТ И ОБУЧЕНИЕ ---
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    register_user(uid, msg.from_user.first_name or "Игрок")
    u = get_user(uid)
    
    if not u[2]:
        bot.send_message(uid, "🌍 *ЭПОХА ИМПЕРИЙ* 🌍\n\nДобро пожаловать в штаб! Выберите государство:", parse_mode="Markdown", reply_markup=empires_kb())
    elif u[20] == 0:
        bot.send_message(uid, f"👑 Приветствую, правитель империи *{u[2]}*!\n\n📖 *ОБУЧЕНИЕ:*\n1️⃣ Нажмите *📊 Статистика*.\n2️⃣ Зайдите в *⚔️ Армия* и наймите пехоту.\n3️⃣ В *💰 Экономика* соберите налоги.\n4️⃣ В *🏗 Постройки* постройте Село.\n5️⃣ В *🗺 Карта* захватите первый регион.\n\nКогда пройдете, нажмите кнопку ниже!", parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Я готов играть!", callback_data="finish_tutorial")))
    else:
        status = "🏴 Под оккупацией!" if u[21] else "🕊 Свободна"
        bot.send_message(uid, f"👑 Приветствую, правитель *{u[2]}*!\nСтатус: {status}", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("emp_"))
def choose_empire(call):
    uid = call.from_user.id; name = call.data[4:]; u = get_user(uid)
    if u[2]: bot.answer_callback_query(call.id, "Уже выбрано!"); return
    db_execute("UPDATE users SET empire=? WHERE user_id=?", (name, uid))
    bot.edit_message_text(f"🏛 Вы возглавили *{name}*!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.send_message(uid, "📜 Вам выдано: 150💰, 150🍖, 150⛏", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "finish_tutorial")
def finish_tutorial(call):
    db_execute("UPDATE users SET tutorial=1 WHERE user_id=?", (call.from_user.id,))
    bot.edit_message_text("🎉 Обучение завершено!", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Империя ждет приказов.", reply_markup=main_menu())

# --- ВЫКУП ИЗ ОККУПАЦИИ ---
@bot.callback_query_handler(func=lambda c: c.data == "buy_freedom")
def buy_freedom(call):
    u = get_user(call.from_user.id)
    if u[21] == 0: bot.answer_callback_query(call.id, "Вы уже свободны!"); return
    if u[3] < 200: bot.answer_callback_query(call.id, "❌ Нужно 200💰 для выкупа!", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-200, occupied_by=0 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "🕊 Вы выкупили независимость!", show_alert=True)

# --- ЭКОНОМИКА ---
@bot.message_handler(func=lambda m: m.text == "💰 Экономика")
def economy(msg):
    u = get_user(msg.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📦 Собрать налоги", callback_data="econ_collect"))
    kb.add(types.InlineKeyboardButton("💱 10⛏ -> 20💰", callback_data="trade_metal"), types.InlineKeyboardButton("💱 20💰 -> 10🍖", callback_data="trade_food"))
    if u[21]: kb.add(types.InlineKeyboardButton("🕊 Выкупить независимость (200💰)", callback_data="buy_freedom"))
    bot.send_message(msg.chat.id, f"💰 *КАЗНА*\n\n💰{u[3]} | 🍖{u[4]} | ⛏{u[5]}\n\n_Сбор раз в 2 минуты._", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "econ_collect")
def econ_collect(call):
    u = get_user(call.from_user.id)
    if time.time() - u[12] < 120: bot.answer_callback_query(call.id, "⏳ Ждите 2 мин!", show_alert=True); return
    
    regs = u[22].split(",") if u[22] else []
    c_add = 30 + (u[18]*8) + (15 if "🏙 Город" in regs else 0)
    f_add = 25 + (u[16]*5) + (10 if "🌾 Поля" in regs else 0)
    m_add = 20 + (u[17]*5) + (10 if "⛰ Горы" in regs else 0)
    
    # Если под оккупацией - отдаем 30% хозяину
    if u[21]:
        owner_id = u[21]
        c_add = int(c_add * 0.7)
        db_execute("UPDATE users SET coins=coins+? WHERE user_id=?", (int(c_add/2), owner_id))

    db_execute("UPDATE users SET coins=coins+?, food=food+?, metal=metal+?, last_collect=? WHERE user_id=?", (c_add, f_add, m_add, int(time.time()), call.from_user.id))
    bot.answer_callback_query(call.id, f"📦 +{c_add}💰 +{f_add}🍖 +{m_add}⛏", show_alert=True)

# --- ПОСТРОЙКИ ---
@bot.message_handler(func=lambda m: m.text == "🏗 Постройки")
def buildings(msg):
    u = get_user(msg.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(f"🏘 Село ур.{u[16]} (+5 еды) - 40💰 20⛏", callback_data="bld_village"))
    kb.add(types.InlineKeyboardButton(f"🏭 Завод ур.{u[17]} (+5 металла) - 40💰 20⛏", callback_data="bld_factory"))
    kb.add(types.InlineKeyboardButton(f"🏪 Магазин ур.{u[18]} (+8 монет) - 50💰 30⛏", callback_data="bld_shop"))
    bot.send_message(msg.chat.id, "🏗 *ИНДУСТРИАЛИЗАЦИЯ*\n\nСтройте здания для пассивного дохода!", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("bld_"))
def build(call):
    uid = call.from_user.id; u = get_user(uid); btype = call.data[4:]
    costs = {"village": (40, 20, 16), "factory": (40, 20, 17), "shop": (50, 30, 18)}
    cost_c, cost_m, idx = costs[btype]
    if u[idx] >= 5: bot.answer_callback_query(call.id, "Максимум 5!", show_alert=True); return
    if u[3] < cost_c or u[5] < cost_m: bot.answer_callback_query(call.id, "❌ Мало ресурсов!", show_alert=True); return
    db_execute(f"UPDATE users SET coins=coins-?, metal=metal-?, {btype}={btype}+1 WHERE user_id=?", (cost_c, cost_m, uid))
    bot.answer_callback_query(call.id, "🏗 Построено!", show_alert=True)

# --- КАРТА ---
@bot.message_handler(func=lambda m: m.text == "🗺 Карта")
def map_menu(msg):
    u = get_user(msg.from_user.id)
    regs = u[22] if u[22] else "Нет"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r_name, r_info in REGIONS.items():
        kb.add(types.InlineKeyboardButton(f"Захватить {r_name} (нужно {r_info['cost']} пехоты)", callback_data=f"reg_{r_name}"))
    bot.send_message(msg.chat.id, f"🗺 *КАРТА МИРА*\n\nВаши регионы: {regs}\n\n_Захват приносит бонус к ресурсам._", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("reg_"))
def capture_region(call):
    uid = call.from_user.id; u = get_user(uid); r_name = call.data[4:]
    cost = REGIONS[r_name]["cost"]
    if u[6] < cost: bot.answer_callback_query(call.id, f"❌ Нужно {cost} пехоты!", show_alert=True); return
    
    if random.randint(1, 100) > 30: 
        regs = u[22].split(",") if u[22] else []
        if r_name not in regs: regs.append(r_name)
        db_execute("UPDATE users SET infantry=infantry-?, regions=?, territories=territories+1 WHERE user_id=?", (cost, ",".join(regs), uid))
        bot.answer_callback_query(call.id, f"🏴 Регион {r_name} захвачен!", show_alert=True)
    else:
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?) WHERE user_id=?", (cost//2, uid))
        bot.answer_callback_query(call.id, "💀 Атака провалилась!", show_alert=True)

# --- ОСТАЛЬНЫЕ ФУНКЦИИ ---
@bot.message_handler(func=lambda m: m.text == "🏛 Империя")
def show_empire(msg):
    u = get_user(msg.from_user.id)
    if not u[2]: bot.send_message(msg.chat.id, "Сначала /start"); return
    status = "🏴 Под оккупацией!" if u[21] else "🕊 Свободна"
    bot.send_message(msg.chat.id, f"🏛 *ГОСУДАРСТВО*\n\nФлаг: {u[2]}\nБонус: _{EMPIRES[u[2]]}_\nСтатус: {status}\n\n🎖 Генерал: {u[13] or 'Нет'}\n🛡 Окопы: {u[15]} ур.\n🗺 Регионы: {u[22] or 'Нет'}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats(msg):
    u = get_user(msg.from_user.id)
    bot.send_message(msg.chat.id, f"📊 *СВОДКА*\n👑 {u[1]} ({u[2]})\n\n💰{u[3]} | 🍖{u[4]} | ⛏{u[5]}\n🛡 Пехота: {u[6]} | 💥 Арт: {u[7]}\n🎖 Ур. армии: {u[11]} | 🛡 Окопы: {u[15]}\n\n🏆{u[8]} | 💀{u[9]} | 🏴{u[10]}\n👤 Генерал: {u[13] or 'Нет'}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "⚔️ Армия")
def army(msg):
    u = get_user(msg.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🛡 Пехота +1", callback_data="rec_inf_1"), types.InlineKeyboardButton("🛡 Пехота +5", callback_data="rec_inf_5"))
    kb.row(types.InlineKeyboardButton("💥 Арт +1", callback_data="rec_art_1"), types.InlineKeyboardButton("💥 Арт +5", callback_data="rec_art_5"))
    kb.row(types.InlineKeyboardButton("⭐ Апгрейд", callback_data="army_lvlup"), types.InlineKeyboardButton("🛡 Окопы", callback_data="build_fort"))
    bot.send_message(msg.chat.id, f"⚔ *АРМИЯ*\nПехота: {u[6]} | Арт: {u[7]}\nУр: {u[11]} | Окопы: {u[15]}", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rec_"))
def recruit(call):
    uid = call.from_user.id; u = get_user(uid); p = call.data.split("_"); n = int(p[2])
    cost = {"c":10, "f":25, "m":15} if p[1] == "inf" else {"c":40, "f":5, "m":60}
    col = "infantry" if p[1] == "inf" else "artillery"
    if u[3] < cost['c']*n or u[4] < cost['f']*n or u[5] < cost['m']*n: bot.answer_callback_query(call.id, "❌ Мало ресурсов!", show_alert=True); return
    db_execute(f"UPDATE users SET coins=coins-?, food=food-?, metal=metal-?, {col}={col}+? WHERE user_id=?", (cost['c']*n, cost['f']*n, cost['m']*n, n, uid))
    bot.answer_callback_query(call.id, f"✅ +{n}!")

@bot.callback_query_handler(func=lambda c: c.data == "army_lvlup")
def army_lvlup(call):
    u = get_user(call.from_user.id)
    if u[11] >= 10: bot.answer_callback_query(call.id, "Максимум 10!", show_alert=True); return
    if u[3] < 50 or u[5] < 40: bot.answer_callback_query(call.id, "❌ Нужно 50💰 40⛏", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-50, metal=metal-40, army_level=army_level+1 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "⭐ Уровень повышен!")

@bot.callback_query_handler(func=lambda c: c.data == "build_fort")
def build_fort(call):
    u = get_user(call.from_user.id)
    if u[15] >= 5: bot.answer_callback_query(call.id, "Максимум 5!", show_alert=True); return
    if u[3] < 30 or u[5] < 50: bot.answer_callback_query(call.id, "❌ Нужно 30💰 50⛏", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-30, metal=metal-50, fortifications=fortifications+1 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "🛡 Окопы!")

@bot.callback_query_handler(func=lambda c: c.data == "trade_metal")
def trade_metal(call):
    u = get_user(call.from_user.id)
    if u[5] < 10: bot.answer_callback_query(call.id, "❌ Нужно 10⛏!", show_alert=True); return
    db_execute("UPDATE users SET metal=metal-10, coins=coins+20 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "💱 Обмен!")

@bot.callback_query_handler(func=lambda c: c.data == "trade_food")
def trade_food(call):
    u = get_user(call.from_user.id)
    if u[3] < 20: bot.answer_callback_query(call.id, "❌ Нужно 20💰!", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-20, food=food+10 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "💱 Обмен!")

@bot.message_handler(func=lambda m: m.text == "🔥 Война")
def war_menu(msg):
    others = [x for x in active_players() if x != msg.from_user.id]
    if not others: bot.send_message(msg.chat.id, "🌐 Нет других игроков."); return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for oid in others:
        ou = get_user(oid); kb.add(types.InlineKeyboardButton(f"⚔ {ou[1]} | 🛡{ou[6]} 💥{ou[7]}", callback_data=f"atk_{oid}"))
    bot.send_message(msg.chat.id, "🔥 *ВОЙНА*", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("atk_"))
def attack(call):
    uid = call.from_user.id; tid = int(call.data[4:]); u = get_user(uid); t = get_user(tid)
    if u[6] + u[7] <= 0: bot.answer_callback_query(call.id, "❌ Нет войск!", show_alert=True); return
    if t[6] + t[7] <= 0: bot.answer_callback_query(call.id, "❌ У врага нет войск!", show_alert=True); return
    atk_p = ((u[6] * 1) + (u[7] * 5)) * (1.0 + (u[11] - 1) * 0.1) + random.randint(0, 10)
    def_p = ((t[6] * 1) + (t[7] * 5)) * (1.0 + (t[11] - 1) * 0.1) * (1.0 + (t[15] * 0.2)) + random.randint(0, 10)
    
    if atk_p > def_p:
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?), artillery=MAX(0,artillery-?), wins=wins+1, coins=coins+30 WHERE user_id=?", (max(1, u[6]//4), max(0, u[7]//5), uid))
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?), artillery=MAX(0,artillery-?), losses=losses+1, coins=MAX(0,coins-20), occupied_by=? WHERE user_id=?", (max(1, t[6]//2), max(0, t[7]//2), uid, tid))
        res = f"🏆 *ТРИУМФ!* {u[1]} разбил {t[1]} и оккупировал его империю!"
    else:
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?), artillery=MAX(0,artillery-?), losses=losses+1 WHERE user_id=?", (max(1, u[6]//2), max(0, u[7]//2), uid))
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?), artillery=MAX(0,artillery-?), wins=wins+1 WHERE user_id=?", (max(1, t[6]//4), max(0, t[7]//4), tid))
        res = f"💀 *РАЗГРОМ!* {u[1]} отступил."
    
    bot.edit_message_text(f"⚔ *БИТВА*\n{res}", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    try: bot.send_message(tid, f"🚨 *ВТОРЖЕНИЕ!*\n{res}", parse_mode="Markdown")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🎖 Генералы")
def heroes(msg):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for h in ["🎩 Наполеон", "🐻 Кутузов", "🦅 Веллингтон", "⚙️ Бисмарк", "🇷🇺 Суворов", "🇺🇸 Грант", "🇯🇵 Того", "👑 Пётр I"]: 
        kb.add(types.InlineKeyboardButton(f"Нанять {h} (100💰)", callback_data=f"hero_{h}"))
    bot.send_message(msg.chat.id, "🎖 *ГЕНШТАБ*\nНаймите генерала.", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("hero_"))
def hire_hero(call):
    u = get_user(call.from_user.id); hero = call.data[5:]
    if u[3] < 100: bot.answer_callback_query(call.id, "❌ Нужно 100💰", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-100, hero=? WHERE user_id=?", (hero, call.from_user.id))
    bot.answer_callback_query(call.id, f"🎖 {hero} нанят!")

@bot.message_handler(func=lambda m: m.text == "🌍 Арена")
def players(msg):
    r = db_execute("SELECT username, empire, infantry, artillery, wins, hero, occupied_by FROM users WHERE empire IS NOT NULL", fetch=True)
    txt = "🌍 *МИРОВАЯ АРЕНА*\n\n"
    if r:
        for row in r: 
            status = " 🏴 Оккупирована" if row[6] else ""
            txt += f"👑 *{row[0]}* — {row[1]}{status}\n🛡{row[2]} 💥{row[3]} 🏆{row[4]} 🎖{row[5] or '—'}\n\n"
    bot.send_message(msg.chat.id, txt, parse_mode="Markdown")

print("🚀 Бот v13.0 (С оккупацией) успешно запущен!")
threading.Thread(target=run_flask).start()
bot.infinity_polling(timeout=30, long_polling_timeout=30)
