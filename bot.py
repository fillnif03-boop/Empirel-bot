import sqlite3, random, time, telebot, threading
from telebot import types
from flask import Flask

TOKEN = "8629585189:AAG2fqhVluKxP5oO64JXrlpHCi-bJFOs8hc" # <--- ВСТАВЬ СВОЙ ТОКЕН СЮДА
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
    farm INTEGER DEFAULT 0, mine INTEGER DEFAULT 0, market INTEGER DEFAULT 0,
    quest_progress INTEGER DEFAULT 0, quest_reward TEXT DEFAULT '', last_quest INTEGER DEFAULT 0,
    tutorial INTEGER DEFAULT 0
)""")

# Добавляем колонки, если их нет
for col in ["farm", "mine", "market", "quest_progress", "last_quest", "tutorial"]:
    try: db_execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
    except: pass
try: db_execute("ALTER TABLE users ADD COLUMN quest_reward TEXT DEFAULT ''")
except: pass

EMPIRES = {
    "🇬🇧 Британская": "Доход +20%", "🇫🇷 Французская": "Атака +15%", "🇩🇪 Германская": "Атака +15%",
    "🇷🇺 Российская": "Армия +15%", "🇦🇹 Австро-Венгрия": "Защита +15%", "🇹🇷 Османская": "Защита +15%",
    "🇯🇵 Японская": "Армия +20%", "🇺🇸 Американская": "Доход +20%", "🇮🇹 Итальянская": "Атака +15%",
    "🇨🇳 Цинская": "Доход +15%"
}

QUESTS = [
    "Найми 5 пехоты", "Найми 2 артиллерии", "Атакуй врага", 
    "Собери налоги 2 раза", "Построй ферму", "Построй шахту"
]

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
    kb.row("💰 Экономика", "🏗 Постройки", "🎖 Генералы")
    kb.row("🔥 Война", "📜 Квесты", "🌍 Арена")
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
        bot.send_message(uid, "🌍 *ЭПОХА ИМПЕРИЙ* 🌍\n\nДобро пожаловать в штаб! Выберите государство, которое будете вести к величию:", parse_mode="Markdown", reply_markup=empires_kb())
    elif u[21] == 0: # Если обучение не пройдено
        bot.send_message(uid, f"👑 Приветствую, правитель империи *{u[2]}*!\n\nЭто краткое обучение. Оно поможет вам освоиться.\n\n1️⃣ Нажмите *📊 Статистика*, чтобы увидеть свои ресурсы.\n2️⃣ Зайдите в *⚔️ Армия* и наймите пехоту.\n3️⃣ В *💰 Экономика* соберите налоги.\n4️⃣ В *🏗 Постройки* постройте ферму.\n\nКогда пройдете эти шаги, нажмите кнопку ниже, чтобы начать играть!", parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Я готов играть!", callback_data="finish_tutorial")))
    else:
        bot.send_message(uid, f"👑 Приветствую, правитель империи *{u[2]}*!\nШтаб готов к работе. Используйте кнопки внизу.", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("emp_"))
def choose_empire(call):
    uid = call.from_user.id; name = call.data[4:]; u = get_user(uid)
    if u[2]: bot.answer_callback_query(call.id, "Вы уже выбрали империю!"); return
    db_execute("UPDATE users SET empire=? WHERE user_id=?", (name, uid))
    bot.edit_message_text(f"🏛 Вы возглавили *{name}*!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.send_message(uid, f"📜 Ваша казна: 150💰, 150🍖, 150⛏.\nСоветую начать с найма армии и постройки фермы!", reply_markup=main_menu())
    # Запуск обучения
    bot.send_message(uid, "Вы только что вступили на трон. Нажмите *📊 Статистика*, чтобы увидеть свои ресурсы.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "finish_tutorial")
def finish_tutorial(call):
    db_execute("UPDATE users SET tutorial=1 WHERE user_id=?", (call.from_user.id,))
    bot.edit_message_text("🎉 Обучение завершено! Империя ждет ваших приказов.", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Управляйте государством с помощью кнопок ниже.", reply_markup=main_menu())

# --- ОСТАЛЬНЫЕ ФУНКЦИИ (без изменений) ---
@bot.message_handler(func=lambda m: m.text == "🏛 Империя")
def show_empire(msg):
    u = get_user(msg.from_user.id)
    if not u[2]: bot.send_message(msg.chat.id, "Сначала выберите империю: /start"); return
    bot.send_message(msg.chat.id, f"🏛 *ГОСУДАРСТВО*\n\nФлаг: {u[2]}\nБонус: _{EMPIRES[u[2]]}_\n\n🎖 Генерал: {u[13] or 'Нет'}\n🛡 Окопы: {u[15]} ур.\n🏭 Ферма: {u[16]} ур. | ⛏ Шахта: {u[17]} ур. | 🏪 Рынок: {u[18]} ур.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats(msg):
    u = get_user(msg.from_user.id)
    bot.send_message(msg.chat.id, f"📊 *СВОДКА ГЕНШТАБА*\n👑 {u[1]} ({u[2]})\n\n💰 Казна: {u[3]} | 🍖 Еда: {u[4]} | ⛏ Металл: {u[5]}\n🛡 Пехота: {u[6]} | 💥 Артиллерия: {u[7]}\n🎖 Ур. армии: {u[11]} | 🛡 Окопы: {u[15]}\n\n🏆 Побед: {u[8]} | 💀 Поражений: {u[9]}\n🏴 Территорий: {u[10]}\n👤 Генерал: {u[13] or 'Нет'}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "⚔️ Армия")
def army(msg):
    u = get_user(msg.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton("🛡 Пехота +1 (10💰)", callback_data="rec_inf_1"), types.InlineKeyboardButton("🛡 Пехота +5 (50💰)", callback_data="rec_inf_5"))
    kb.row(types.InlineKeyboardButton("💥 Арт +1 (40💰)", callback_data="rec_art_1"), types.InlineKeyboardButton("💥 Арт +5 (200💰)", callback_data="rec_art_5"))
    kb.row(types.InlineKeyboardButton("⭐ Апгрейд (50💰 40⛏)", callback_data="army_lvlup"), types.InlineKeyboardButton("🛡 Рыть окопы (30💰 50⛏)", callback_data="build_fort"))
    bot.send_message(msg.chat.id, f"⚔ *ВОЕННОЕ МИНИСТЕРСТВО*\n\nУ вас: {u[6]} пехоты | {u[7]} артиллерии\nУровень армии: {u[11]}\nОкопы: {u[15]} ур.\n\n_Артиллерия в 5 раз сильнее пехоты!_", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rec_"))
def recruit(call):
    uid = call.from_user.id; u = get_user(uid); p = call.data.split("_"); n = int(p[2])
    cost = {"c":10, "f":25, "m":15} if p[1] == "inf" else {"c":40, "f":5, "m":60}
    col = "infantry" if p[1] == "inf" else "artillery"
    nc, nf, nm = cost['c']*n, cost['f']*n, cost['m']*n
    if u[3] < nc or u[4] < nf or u[5] < nm: bot.answer_callback_query(call.id, "❌ Не хватает ресурсов!", show_alert=True); return
    db_execute(f"UPDATE users SET coins=coins-?, food=food-?, metal=metal-?, {col}={col}+? WHERE user_id=?", (nc, nf, nm, n, uid))
    bot.answer_callback_query(call.id, f"✅ Нанято {n}!")

@bot.callback_query_handler(func=lambda c: c.data == "army_lvlup")
def army_lvlup(call):
    u = get_user(call.from_user.id)
    if u[11] >= 10: bot.answer_callback_query(call.id, "Максимум 10!", show_alert=True); return
    if u[3] < 50 or u[5] < 40: bot.answer_callback_query(call.id, "❌ Нужно 50💰 40⛏", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-50, metal=metal-40, army_level=army_level+1 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "⭐ Уровень повышен!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "build_fort")
def build_fort(call):
    u = get_user(call.from_user.id)
    if u[15] >= 5: bot.answer_callback_query(call.id, "Максимум 5!", show_alert=True); return
    if u[3] < 30 or u[5] < 50: bot.answer_callback_query(call.id, "❌ Нужно 30💰 50⛏", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-30, metal=metal-50, fortifications=fortifications+1 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "🛡 Окопы углублены!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "🏗 Постройки")
def buildings(msg):
    u = get_user(msg.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(f"🌾 Ферма ур.{u[16]} (+5 еды) - 40💰 20⛏", callback_data="bld_farm"))
    kb.add(types.InlineKeyboardButton(f"⛏ Шахта ур.{u[17]} (+5 металла) - 40💰 20⛏", callback_data="bld_mine"))
    kb.add(types.InlineKeyboardButton(f"🏪 Рынок ур.{u[18]} (+8 монет) - 50💰 30⛏", callback_data="bld_market"))
    bot.send_message(msg.chat.id, "🏗 *ИНДУСТРИАЛИЗАЦИЯ*\n\nСтройте здания для пассивного дохода!", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("bld_"))
def build(call):
    uid = call.from_user.id; u = get_user(uid); btype = call.data[4:]
    costs = {"farm": (40, 20, 16), "mine": (40, 20, 17), "market": (50, 30, 18)}
    cost_c, cost_m, idx = costs[btype]
    if u[idx] >= 5: bot.answer_callback_query(call.id, "Максимальный уровень!", show_alert=True); return
    if u[3] < cost_c or u[5] < cost_m: bot.answer_callback_query(call.id, "❌ Мало ресурсов!", show_alert=True); return
    db_execute(f"UPDATE users SET coins=coins-?, metal=metal-?, {btype}={btype}+1 WHERE user_id=?", (cost_c, cost_m, uid))
    bot.answer_callback_query(call.id, "🏗 Построено!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "💰 Экономика")
def economy(msg):
    u = get_user(msg.from_user.id)
    income = 30 + (u[18]*8)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📦 Собрать налоги", callback_data="econ_collect"))
    kb.add(types.InlineKeyboardButton("💱 Обмен: 10⛏ -> 20💰", callback_data="trade_metal"), types.InlineKeyboardButton("💱 Обмен: 20💰 -> 10🍖", callback_data="trade_food"))
    bot.send_message(msg.chat.id, f"💰 *МИНИСТЕРСТВО ФИНАНСОВ*\n\n💰{u[3]} | 🍖{u[4]} | ⛏{u[5]}\n\nДоход: ~{income}💰\n_Сбор раз в 2 минуты._", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "econ_collect")
def econ_collect(call):
    u = get_user(call.from_user.id)
    if time.time() - u[12] < 120: bot.answer_callback_query(call.id, "⏳ Ждите 2 мин!", show_alert=True); return
    c_add = 30 + u[18]*8; f_add = 25 + u[16]*5; m_add = 20 + u[17]*5
    db_execute("UPDATE users SET coins=coins+?, food=food+?, metal=metal+?, last_collect=? WHERE user_id=?", (c_add, f_add, m_add, int(time.time()), call.from_user.id))
    bot.answer_callback_query(call.id, f"📦 +{c_add}💰 +{f_add}🍖 +{m_add}⛏", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "trade_metal")
def trade_metal(call):
    u = get_user(call.from_user.id)
    if u[5] < 10: bot.answer_callback_query(call.id, "❌ Нужно 10⛏!", show_alert=True); return
    db_execute("UPDATE users SET metal=metal-10, coins=coins+20 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "💱 Обменяно!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "trade_food")
def trade_food(call):
    u = get_user(call.from_user.id)
    if u[3] < 20: bot.answer_callback_query(call.id, "❌ Нужно 20💰!", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-20, food=food+10 WHERE user_id=?", (call.from_user.id,))
    bot.answer_callback_query(call.id, "💱 Обменяно!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "📜 Квесты")
def quests(msg):
    u = get_user(msg.from_user.id)
    now = int(time.time())
    if now - u[20] > 86400 or not u[19]:
        q = random.choice(QUESTS)
        db_execute("UPDATE users SET quest_reward=?, quest_progress=0, last_quest=? WHERE user_id=?", (q, now, msg.from_user.id))
        bot.send_message(msg.chat.id, f"📜 *ВОЕННЫЙ СОВЕТ*\n\nНовое задание: *{q}*\nНаграда: 100💰, 50🍖, 50⛏", parse_mode="Markdown")
    else:
        bot.send_message(msg.chat.id, f"📜 *ВОЕННЫЙ СОВЕТ*\n\nТекущее: *{u[19]}*\n\n_Выполните его для награды!_", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔥 Война")
def war_menu(msg):
    others = [x for x in active_players() if x != msg.from_user.id]
    if not others: bot.send_message(msg.chat.id, "🌐 Нет других игроков."); return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for oid in others:
        ou = get_user(oid); kb.add(types.InlineKeyboardButton(f"⚔ {ou[1]} ({ou[2]}) | 🛡{ou[6]} 💥{ou[7]}", callback_data=f"atk_{oid}"))
    bot.send_message(msg.chat.id, "🔥 *ВОЙНА*\nВыберите цель. Остерегайтесь окопов!", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("atk_"))
def attack(call):
    uid = call.from_user.id; tid = int(call.data[4:]); u = get_user(uid); t = get_user(tid)
    if u[6] + u[7] <= 0: bot.answer_callback_query(call.id, "❌ Нет войск!", show_alert=True); return
    if t[6] + t[7] <= 0: bot.answer_callback_query(call.id, "❌ У врага нет войск!", show_alert=True); return
    atk_p = ((u[6] * 1) + (u[7] * 5)) * (1.0 + (u[11] - 1) * 0.1) + random.randint(0, 10)
    def_p = ((t[6] * 1) + (t[7] * 5)) * (1.0 + (t[11] - 1) * 0.1) * (1.0 + (t[15] * 0.2)) + random.randint(0, 10)
    if atk_p > def_p:
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?), artillery=MAX(0,artillery-?), wins=wins+1, coins=coins+30 WHERE user_id=?", (max(1, u[6]//4), max(0, u[7]//5), uid))
        db_execute("UPDATE users SET infantry=MAX(0,infantry-?), artillery=MAX(0,artillery-?), losses=losses+1, coins=MAX(0,coins-20) WHERE user_id=?", (max(1, t[6]//2), max(0, t[7]//2), tid))
        res = f"🏆 *ТРИУМФ!* {u[1]} разбил {t[1]}."
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
    bot.send_message(msg.chat.id, "🎖 *ГЕНЕРАЛЬНЫЙ ШТАБ*\n\nНаймите генерала для бонусов.", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("hero_"))
def hire_hero(call):
    u = get_user(call.from_user.id); hero = call.data[5:]
    if u[3] < 100: bot.answer_callback_query(call.id, "❌ Нужно 100💰", show_alert=True); return
    db_execute("UPDATE users SET coins=coins-100, hero=? WHERE user_id=?", (hero, call.from_user.id))
    bot.answer_callback_query(call.id, f"🎖 {hero} нанят!", show_alert=True)

@bot.message_handler(func=lambda m: m.text == "🌍 Арена")
def players(msg):
    r = db_execute("SELECT username, empire, infantry, artillery, wins, hero FROM users WHERE empire IS NOT NULL", fetch=True)
    txt = "🌍 *МИРОВАЯ АРЕНА*\n\n"
    if r:
        for row in r: txt += f"👑 *{row[0]}* — {row[1]}\n🛡{row[2]} 💥{row[3]} 🏆{row[4]} 🎖{row[5] or '—'}\n\n"
    bot.send_message(msg.chat.id, txt, parse_mode="Markdown")

print("🚀 Бот v10.0 (С обучением) успешно запущен!")
threading.Thread(target=run_flask).start()
bot.infinity_polling(timeout=30, long_polling_timeout=30)
