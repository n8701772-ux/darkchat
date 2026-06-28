
import os
import logging
import json
import asyncio
from asyncio import start_server
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes
)

# ==================== ТОКЕН ====================
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("ERROR: BOT_TOKEN not found!")

# ==================== НАСТРОЙКИ ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERS_FILE = "dark_users.json"
PAIRS_FILE = "dark_pairs.json"
QUEUE_FILE = "dark_queue.json"

# ==================== БАЗА ДАННЫХ ====================
def load_json(filepath, default_type):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default_type
    return default_type

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users(): return load_json(USERS_FILE, {})
def save_users(users): save_json(USERS_FILE, users)
def load_pairs(): return load_json(PAIRS_FILE, {})
def save_pairs(pairs): save_json(PAIRS_FILE, pairs)
def load_queue(): 
    q = load_json(QUEUE_FILE, [])
    # Очистка старой очереди, если там остались просто ID вместо словарей
    if q and isinstance(q[0], str): return []
    return q
def save_queue(queue): save_json(QUEUE_FILE, queue)

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["/search 🔍 Найти собеседника", "/stop ⏹ Остановить диалог"],
        ["/profile 👤 Мой профиль", "/game 🎮 Играть с собеседником"],
        ["/referrals 👥 Рефералы", "/donate 💖 Поддержать создателей"],
        ["/about ℹ️ О чате"]
    ], resize_keyboard=True)

def gender_setup_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨 Я Парень", callback_data="setgen_M"),
         InlineKeyboardButton("👩 Я Девушка", callback_data="setgen_F")]
    ])

def search_preferences_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨 Парня", callback_data="look_M"),
         InlineKeyboardButton("👩 Девушку", callback_data="look_F")],
        [InlineKeyboardButton("🎲 Без разницы", callback_data="look_any")]
    ])

def donate_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 50 Stars", callback_data="donate_50"),
         InlineKeyboardButton("⭐ 100 Stars", callback_data="donate_100")],
        [InlineKeyboardButton("⭐ 250 Stars", callback_data="donate_250"),
         InlineKeyboardButton("⭐ 500 Stars", callback_data="donate_500")]
    ])

def chat_games_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Бросить кубики", callback_data="chatgame_dice")],
        [InlineKeyboardButton("🎯 Сыграть в Дартс", callback_data="chatgame_darts")]
    ])

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    
    if user_id not in users:
        users[user_id] = {
            "name": update.effective_user.first_name,
            "username": update.effective_user.username or "Без ника",
            "gender": "none",
            "donated": 0,
            "referrals": 0,
            "register_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
    
    text = (
        f"🌑 <b>ДОБРО ПОЖАЛОВАТЬ В DARK ANON CHAT!</b>\n\n"
        f"🔮 <i>Анонимный чат с умным поиском.</i>\n\n"
        f"Используй меню ниже для управления ботом!"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    pairs = load_pairs()
    queue = load_queue()
    user = users.get(user_id, {})
    
    if user_id in pairs:
        await update.message.reply_text("⚠️ Вы уже в диалоге! Сначала завершите его командой /stop")
        return
    if any(q['id'] == user_id for q in queue):
        await update.message.reply_text("🔍 Вы уже в очереди поиска. Пожалуйста, подождите...")
        return

    # Если пол не установлен
    if user.get("gender", "none") == "none":
        await update.message.reply_text("❗️ <b>Для начала поиска укажите ваш пол:</b>", parse_mode="HTML", reply_markup=gender_setup_kb())
        return

    # Запрашиваем, кого искать
    await update.message.reply_text("🔍 <b>Кого вы хотите найти?</b>", parse_mode="HTML", reply_markup=search_preferences_kb())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    queue = load_queue()
    stopped = False
    
    # Ищем в очереди и удаляем
    for i, q in enumerate(queue):
        if q['id'] == user_id:
            del queue[i]
            save_queue(queue)
            await update.message.reply_text("⏹ <b>Поиск отменен.</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
            stopped = True
            break
            
    # Ищем в парах и удаляем
    if user_id in pairs:
        partner_id = pairs.pop(user_id)
        if partner_id in pairs:
            pairs.pop(partner_id)
        save_pairs(pairs)
        
        await update.message.reply_text("⏹ <b>Вы завершили диалог.</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
        try:
            await context.bot.send_message(chat_id=partner_id, text="⏹ <b>Собеседник покинул чат.</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
        except: pass
        stopped = True
        
    if not stopped:
        await update.message.reply_text("❌ Вы сейчас ни с кем не общаетесь и не находитесь в поиске.", reply_markup=get_main_keyboard())

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    gen_text = "👨 Парень" if user.get('gender') == 'M' else ("👩 Девушка" if user.get('gender') == 'F' else "Не указан")
    
    await update.message.reply_text(
        f"🌌 <b>ТВОЙ DARK ПРОФИЛЬ</b>\n\n"
        f"⚧ Ваш пол: <b>{gen_text}</b>\n"
        f"👥 Приглашено друзей: <code>{user.get('referrals', 0)} чел.</code>\n"
        f"💖 Отправлено на поддержку: <code>{user.get('donated', 0)} ⭐</code>",
        parse_mode="HTML", reply_markup=get_main_keyboard()
    )

async def cmd_donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💖 <b>ПОДДЕРЖКА СОЗДАТЕЛЕЙ</b>\n\n"
        f"Проект существует на энтузиазме! Если вам нравится бот, вы можете поддержать нас на любую сумму.",
        parse_mode="HTML", reply_markup=donate_kb()
    )

async def cmd_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    await update.message.reply_text(
        f"👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"Ваших рефералов: <code>{user.get('referrals', 0)}</code>\n\n"
        f"🔗 <b>Твоя инвайт-ссылка:</b>\n"
        f"<code>https://t.me/{context.bot.username}?start=ref_{user_id}</code>",
        parse_mode="HTML", reply_markup=get_main_keyboard()
    )

async def cmd_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    if user_id in pairs:
        await update.message.reply_text("🎮 <b>Выберите игру для вызова собеседника:</b>", parse_mode="HTML", reply_markup=chat_games_kb())
    else:
        await update.message.reply_text("⚠️ Игры доступны только во время общения с собеседником!")

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌑 <b>DARK ANON CHAT</b>\n\n• Версия: <code>5.0 Smart Match</code>\n• Умный подбор по полу\n• Игры в чате", parse_mode="HTML", reply_markup=get_main_keyboard())

# ==================== ОПЛАТА ПОДДЕРЖКИ ====================
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    amount = update.message.successful_payment.total_amount
    
    user['donated'] = user.get('donated', 0) + amount
    users[user_id] = user
    save_users(users)
    await update.message.reply_text(f"🎉 <b>Огромное спасибо за поддержку!</b> Вы пожертвовали {amount} ⭐.", parse_mode="HTML", reply_markup=get_main_keyboard())

# ==================== ОБРАБОТКА ТЕКСТА И ФОТО ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    
    # Обработка команд из кнопок
    if text.startswith("/search"): await cmd_search(update, context); return
    elif text.startswith("/stop"): await cmd_stop(update, context); return
    elif text.startswith("/profile"): await cmd_profile(update, context); return
    elif text.startswith("/donate"): await cmd_donate(update, context); return
    elif text.startswith("/referrals"): await cmd_referrals(update, context); return
    elif text.startswith("/game"): await cmd_game(update, context); return
    elif text.startswith("/about"): await cmd_about(update, context); return

    if user_id in pairs:
        partner_id = pairs[user_id]
        try:
            # ДОБАВЛЯЕМ ЗНАЧОК 💬 В КОНЦЕ СООБЩЕНИЯ
            await context.bot.send_message(chat_id=partner_id, text=f"{text} 💬")
        except: await cmd_stop(update, context)
    else:
        await update.message.reply_text("⚠️ <b>Вы не в диалоге!</b> Нажмите <code>/search</code>.", parse_mode="HTML", reply_markup=get_main_keyboard())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    if user_id in pairs:
        partner_id = pairs[user_id]
        photo = update.message.photo[-1]
        try:
            await context.bot.send_photo(chat_id=partner_id, photo=photo.file_id, caption="📸")
        except: await cmd_stop(update, context)
    else:
        await update.message.reply_text("⚠️ Фотографии можно отправлять только во время активного диалога!")

# ==================== ИНЛАЙН КНОПКИ И ПОИСК ====================
def find_match(queue, user_id, user_gen, look_for):
    for i, p in enumerate(queue):
        if p['id'] == user_id: continue
        
        # Проверяем, подходит ли человек из очереди нашему юзеру
        match1 = (look_for == 'any') or (look_for == p['gen'])
        # Проверяем, подходит ли наш юзер человеку из очереди
        match2 = (p['look'] == 'any') or (p['look'] == user_gen)
        
        if match1 and match2:
            return queue.pop(i)
    return None

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    users = load_users()
    user = users.get(user_id, {})
    data = query.data
    
    # 1. Установка пола
    if data.startswith("setgen_"):
        gender = data.split("_")[1]
        user['gender'] = gender
        users[user_id] = user
        save_users(users)
        gen_str = "Парнем" if gender == "M" else "Девушкой"
        await query.edit_message_text(f"✅ Вы успешно зарегистрировались как: <b>{gen_str}</b>\nТеперь нажмите /search еще раз!", parse_mode="HTML")
    
    # 2. Логика поиска
    elif data.startswith("look_"):
        look_for = data.split("_")[1]
        user_gen = user.get('gender')
        pairs = load_pairs()
        queue = load_queue()
        
        # Ищем совпадение
        match = find_match(queue, user_id, user_gen, look_for)
        
        if match:
            partner_id = match['id']
            pairs[user_id] = partner_id
            pairs[partner_id] = user_id
            save_pairs(pairs)
            save_queue(queue)
            
            success_msg = "🔮 <b>Собеседник найден! Приятного общения.</b>"
            await query.edit_message_text(success_msg, parse_mode="HTML")
            try:
                await context.bot.send_message(chat_id=partner_id, text=success_msg, parse_mode="HTML")
            except: pass
        else:
            # Очищаем старые заявки этого юзера и добавляем новую
            queue = [q for q in queue if q['id'] != user_id]
            queue.append({'id': user_id, 'gen': user_gen, 'look': look_for})
            save_queue(queue)
            await query.edit_message_text("🔍 <b>Ищем подходящего собеседника...</b>\n\nОстановить поиск можно кнопкой /stop", parse_mode="HTML")

    # 3. Донат
    elif data.startswith("donate_"):
        amount = int(data.split("_")[1])
        prices = [LabeledPrice(f"Поддержка {amount} Звезд", amount)]
        await context.bot.send_invoice(chat_id=query.message.chat_id, title="Поддержка проекта", description=f"Отправить разработчикам {amount} Stars", payload="support_donate", provider_token="", currency="XTR", prices=prices)

    # 4. Игры в чате
    elif data.startswith("chatgame_"):
        pairs = load_pairs()
        if user_id in pairs:
            partner_id = pairs[user_id]
            game_type = data.split("_")[1]
            emoji = "🎲" if game_type == "dice" else "🎯"
            await query.edit_message_text(f"Вы отправили вызов {emoji} собеседнику!")
            
            # Отправляем анимацию обоим
            await context.bot.send_message(chat_id=user_id, text="Ваш бросок:")
            await context.bot.send_dice(chat_id=user_id, emoji=emoji)
            
            try:
                await context.bot.send_message(chat_id=partner_id, text="Собеседник бросает вызов! Его бросок:")
                await context.bot.send_dice(chat_id=partner_id, emoji=emoji)
                await context.bot.send_message(chat_id=partner_id, text="Отправьте /game чтобы бросить в ответ!")
            except: pass
        else:
            await query.edit_message_text("⚠️ Вы не в диалоге.")

# ==================== СЕРВЕР ДЛЯ РЕНДЕРА ====================
async def handle_ping(reader, writer):
    try:
        await reader.read(1024)
        writer.write("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\nБот активен!".encode('utf-8'))
        await writer.drain()
    except: pass
    finally: writer.close()

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = await start_server(handle_ping, '0.0.0.0', port)
    asyncio.create_task(server.serve_forever())

# ==================== ЗАПУСК ====================
async def run_bot():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("donate", cmd_donate))
    app.add_handler(CommandHandler("game", cmd_game))
    app.add_handler(CommandHandler("referrals", cmd_referrals))
    app.add_handler(CommandHandler("about", cmd_about))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    logger.info("🌑 БОТ УСПЕШНО ЗАПУЩЕН!")
    while True: await asyncio.sleep(3600)

def main():
    for f in [USERS_FILE, PAIRS_FILE, QUEUE_FILE]:
        if not os.path.exists(f): save_json(f, {} if f != QUEUE_FILE else [])
            
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_web_server())
    loop.run_until_complete(run_bot())

if __name__ == "__main__":
    main()

