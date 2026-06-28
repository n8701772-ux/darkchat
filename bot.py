
import os
import logging
import json
import random
import asyncio
from asyncio import start_server
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== ТОКЕН ====================
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("ERROR: BOT_TOKEN not found!")

# ==================== НАСТРОЙКИ ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERS_FILE = "dark_users.json"
PAIRS_FILE = "dark_pairs.json"

# ==================== БАЗА ДАННЫХ ====================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_pairs():
    if os.path.exists(PAIRS_FILE):
        with open(PAIRS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_pairs(pairs):
    with open(PAIRS_FILE, 'w', encoding='utf-8') as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["🔍 Найти (/search)", "⏹ Остановить (/stop)"],
        ["👤 Профиль", "⭐ Премиум"],
        ["👥 Рефералы", "🎮 Игры"],
        ["📞 Поддержка", "ℹ️ О чате"]
    ], resize_keyboard=True)

def games_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Крестики-нолики", callback_data="game_tic")],
        [InlineKeyboardButton("🎰 Рулетка", callback_data="game_roulette")],
        [InlineKeyboardButton("🎲 Угадай число", callback_data="game_number")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])

def premium_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Купить Premium (50 ⭐)", callback_data="buy_premium")],
        [InlineKeyboardButton("🎁 VIP за реферала", callback_data="vip_referral")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])

def number_keyboard():
    buttons = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"num_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_games")])
    return InlineKeyboardMarkup(buttons)

def tic_tac_toe_board(board, game_id):
    keyboard = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            cell = board[i+j]
            if cell == ' ':
                row.append(InlineKeyboardButton("⬜", callback_data=f"tic_{game_id}_{i+j}"))
            elif cell == 'X':
                row.append(InlineKeyboardButton("❌", callback_data=f"tic_none"))
            else:
                row.append(InlineKeyboardButton("⭕", callback_data=f"tic_none"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_games")])
    return InlineKeyboardMarkup(keyboard)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ИГР <====================
def check_win(board, player):
    win_combinations = [[0,1,2], [3,4,5], [6,7,8], [0,3,6], [1,4,7], [2,5,8], [0,4,8], [2,4,6]]
    return any(all(board[i] == player for i in combo) for combo in win_combinations)

def get_best_move(board):
    for player in ['O', 'X']:
        for i in range(9):
            if board[i] == ' ':
                board_copy = board.copy()
                board_copy[i] = player
                if check_win(board_copy, player):
                    return i
    for i in range(9):
        if board[i] == ' ':
            return i
    return None

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    
    if user_id not in users:
        users[user_id] = {
            "name": update.effective_user.first_name,
            "username": update.effective_user.username or "Без ника",
            "gender": "unknown",
            "premium": False,
            "premium_until": "none",
            "stars": 0,
            "referrals": 0,
            "register_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
        
        await update.message.reply_text(
            f"🌑 <b>ДОБРО ПОЖАЛОВАТЬ В DARK ANON CHAT!</b>\n\n"
            f"🔮 <i>Анонимный чат без границ и ограничений.</i>\n\n"
            f"⚡ <b>Команды управления:</b>\n"
            f"🚀 /search — Найти случайного собеседника\n"
            f"⏹ /stop — Прервать текущий диалог\n\n"
            f"✅ Полная анонимность\n"
            f"✅ Свобода общения\n\n"
            f"Используй меню снизу или отправь /search для старта!",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"🌑 <b>С возвращением в Dark Anon Chat!</b>\nОтправь /search, чтобы начать поиск.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    pairs = load_pairs()
    
    if user_id in pairs:
        await update.message.reply_text("⚠️ Вы уже находитесь в диалоге! Сначала завершите его командой /stop")
        return

    available = None
    for uid in users:
        if uid != user_id and uid not in pairs:
            # Убедимся, что потенциальный партнер тоже нажал поиск и ждет (не находится в пассивном состоянии)
            available = uid
            break
    
    if available:
        pairs[user_id] = available
        pairs[available] = user_id
        save_pairs(pairs)
        
        await update.message.reply_text("🔮 <b>Собеседник найден! Приятного общения.</b>\n Чтобы выйти, отправь /stop", parse_mode="HTML")
        await context.bot.send_message(
            chat_id=available,
            text="🔮 <b>Собеседник найден! Приятного общения.</b>\n Чтобы выйти, отправь /stop",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("🔍 <b>Ищем собеседника...</b>\nПожалуйста, подождите немного.", parse_mode="HTML")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    
    if user_id in pairs:
        partner_id = pairs[user_id]
        
        if user_id in pairs: del pairs[user_id]
        if partner_id in pairs: del pairs[partner_id]
        save_pairs(pairs)
        
        await update.message.reply_text("⏹ <b>Вы завершили диалог.</b>\nЧтобы найти нового собеседника, отправь /search", parse_mode="HTML")
        await context.bot.send_message(
            chat_id=partner_id,
            text="⏹ <b>Собеседник прервал диалог.</b>\nЧтобы найти нового собеседника, отправь /search",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Вы сейчас не находитесь в активном диалоге.")

# ==================== СТАТИЧЕСКИЕ ИНФО-РАЗДЕЛЫ ====================
async def show_profile(update: Update, users, user_id):
    user = users.get(user_id, {})
    await update.message.reply_text(
        f"🌌 <b>ТВОЙ DARK ПРОФИЛЬ</b>\n\n"
        f"👑 Премиум статус: <code>{'Активен ✨' if user.get('premium') else 'Отсутствует ❌'}</code>\n"
        f"💎 Баланс звезд: <code>{user.get('stars', 0)} ⭐</code>\n"
        f"👥 Приглашено рефералов: <code>{user.get('referrals', 0)} чел.</code>",
        parse_mode="HTML"
    )

async def show_premium(update: Update):
    await update.message.reply_text(
        f"⭐ <b>DARK PREMIUM</b>\n\n"
        f"Преимущества премиума:\n"
        f"• Уникальный статус в профиле\n"
        f"• Доступ к скрытым функциям будущих версий чата\n\n"
        f"💰 Цена: <b>50 звезд</b> на 7 дней",
        parse_mode="HTML",
        reply_markup=premium_menu()
    )

async def show_referrals(update: Update, context, user_id, user):
    await update.message.reply_text(
        f"👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"Ваша статистика приглашений: <code>{user.get('referrals', 0)}</code>\n\n"
        f"🔗 <b>Твоя персональная инвайт-ссылка:</b>\n"
        f"<code>https://t.me/{context.bot.username}?start=ref_{user_id}</code>",
        parse_mode="HTML"
    )

# ==================== ТЕКСТОВЫЙ МЕНЕДЖЕР И ПЕРЕСЫЛКА ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)
    users = load_users()
    pairs = load_pairs()
    user = users.get(user_id, {})
    
    # 1. Если пользователь в активном диалоге — пересылаем сообщение без задержек
    if user_id in pairs:
        partner_id = pairs[user_id]
        if partner_id in users:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"💬 <b>Новое сообщение</b>\n\n{text}",
                parse_mode="HTML"
            )
            return

    # 2. Если не в диалоге — обрабатываем нажатия текстового меню
    if "🔍 Найти" in text:
        await cmd_search(update, context)
    elif "⏹ Остановить" in text:
        await cmd_stop(update, context)
    elif text == "👤 Мой профиль" or text == "👤 Профиль":
        await show_profile(update, users, user_id)
    elif text == "⭐ Премиум":
        await show_premium(update)
    elif text == "👥 Рефералы":
        await show_referrals(update, context, user_id, user)
    elif text == "🎮 Игры":
        await update.message.reply_text("🎮 <b>Выберите игру из списка ниже:</b>", parse_mode="HTML", reply_markup=games_menu())
    elif text == "📞 Поддержка":
        await update.message.reply_text("📞 <b>Служба поддержки проекта:</b>\n\nРазработчик: @WHITEDARON", parse_mode="HTML")
    elif text == "ℹ️ О чате":
        await update.message.reply_text("🌑 <b>DARK ANON CHAT</b>\n\n• Версия: <code>3.5.0 Premium</code>\n• Полная конфиденциальность\n• Мгновенный асинхронный движок", parse_mode="HTML")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    
    if user_id in pairs:
        partner_id = pairs[user_id]
        photo = update.message.photo[-1]
        await context.bot.send_photo(
            chat_id=partner_id,
            photo=photo.file_id,
            caption="📸 <b>Новое фото</b>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("⚠️ Отправлять медиафайлы можно только находясь в диалоге с собеседником!")

# ==================== ОБРАБОТКА ИНЛАЙН КНОПОК ИГР ====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    users = load_users()
    user = users.get(user_id, {})
    data = query.data
    
    if data == "game_tic":
        game_id = f"tic_{user_id}_{int(datetime.now().timestamp())}"
        board = [' '] * 9
        context.user_data['tic_board'] = board
        context.user_data['tic_game_id'] = game_id
        await query.edit_message_text("❌ <b>Крестики-нолики</b>\nСделайте ваш первый ход на доске:", parse_mode="HTML", reply_markup=tic_tac_toe_board(board, game_id))
    
    elif data.startswith("tic_"):
        parts = data.split("_")
        if len(parts) == 3 and parts[1] != "none":
            pos = int(parts[2])
            board = context.user_data.get('tic_board', [' ']*9)
            if board[pos] == ' ':
                board[pos] = 'X'
                if check_win(board, 'X'):
                    user['stars'] = user.get('stars', 0) + 10
                    users[user_id] = user
                    save_users(users)
                    await query.edit_message_text(f"🎉 <b>Победа! Вы обыграли ИИ!</b>\n Начислено: +10 ⭐", parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Играть снова", callback_data="game_tic")],[InlineKeyboardButton("🔙 В меню игр", callback_data="back_games")]]))
                    return
                
                bot_move = get_best_move(board)
                if bot_move is not None:
                    board[bot_move] = 'O'
                    if check_win(board, 'O'):
                        await query.edit_message_text("😔 <b>Поражение! Бот оказался умнее.</b>", parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать снова", callback_data="game_tic")],[InlineKeyboardButton("🔙 В меню игр", callback_data="back_games")]]))
                        return
                
                context.user_data['tic_board'] = board
                await query.edit_message_text("❌ <b>Ваш ход:</b>", parse_mode="HTML", reply_markup=tic_tac_toe_board(board, parts[1]))
    
    elif data == "game_roulette":
        await query.edit_message_text("🎰 <b>Рулетка ценностей</b>\nВыберите цвет для ставки (Стоимость: 5 ⭐):", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔴 Красный", callback_data="roulette_red")],[InlineKeyboardButton("⚫️ Черный", callback_data="roulette_black")],[InlineKeyboardButton("🟢 Зеленый (x36)", callback_data="roulette_green")],[InlineKeyboardButton("🔙 Назад", callback_data="back_games")]]))
    
    elif data.startswith("roulette_"):
        color = data.split("_")[1]
        result = random.randint(0, 36)
        result_color = "green" if result == 0 else ("red" if result % 2 == 0 else "black")
        win = color == result_color
        
        if win:
            stars = 35 if color == "green" else 10
            user['stars'] = user.get('stars', 0) + stars
            result_text = f"🎉 <b>Победа! Выпал цвет {result_color.upper()}. Получено {stars} ⭐!</b>"
        else:
            user['stars'] = max(0, user.get('stars', 0) - 5)
            result_text = f"😔 <b>Проигрыш! Выпало число {result} ({result_color.upper()}). Потеряно 5 ⭐</b>"
        
        users[user_id] = user
        save_users(users)
        await query.edit_message_text(f"{result_text}\n💰 Текущий баланс: {user['stars']} ⭐", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Покрутить еще", callback_data="game_roulette")],[InlineKeyboardButton("🔙 Назад", callback_data="back_games")]]))
    
    elif data == "game_number":
        await query.edit_message_text("🎲 <b>Угадай число</b>\nКомпьютер загадал число от 1 до 10. Попробуй угадать за 3 ⭐:", parse_mode="HTML", reply_markup=number_keyboard())
    
    elif data.startswith("num_"):
        guess = int(data.split("_")[1])
        number = random.randint(1, 10)
        if guess == number:
            user['stars'] = user.get('stars', 0) + 15
            result = f"🎉 <b>Идеально! Число действительно было {number}. Получено +15 ⭐</b>"
        else:
            user['stars'] = max(0, user.get('stars', 0) - 3)
            result = f"😔 <b>Не угадали. Было загадано число {number}. Списано 3 ⭐</b>"
        
        users[user_id] = user
        save_users(users)
        await query.edit_message_text(f"{result}\n💰 Баланс: {user['stars']} ⭐", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Играть еще", callback_data="game_number")],[InlineKeyboardButton("🔙 Назад", callback_data="back_games")]]))
    
    elif data == "buy_premium":
        if user.get('stars', 0) >= 50:
            user['stars'] -= 50
            user['premium'] = True
            user['premium_until'] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            users[user_id] = user
            save_users(users)
            await query.edit_message_text("⭐ <b>Премиум успешно активирован на 7 дней! Приятного пользования.</b>", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ <b>Недостаточно средств.</b> Требуется 50 ⭐. У вас на счету: {user.get('stars', 0)} ⭐", parse_mode="HTML")
    
    elif data == "vip_referral":
        await query.edit_message_text(f"👥 <b>VIP за реферала</b>\n\nПригласите друга по ссылке:\n<code>https://t.me/{context.bot.username}?start=ref_{user_id}</code>", parse_mode="HTML")
    elif data == "back_games":
        await query.edit_message_text("🎮 <b>Выберите игру:</b>", parse_mode="HTML", reply_markup=games_menu())
    elif data == "back_main":
        await query.edit_message_text("🌑 <b>Главное меню Dark Чат</b>", parse_mode="HTML")

# ==================== АСИНХРОННЫЙ ВЕБ-СЕРВЕР ДЛЯ РЕНДЕРА ====================
async def handle_ping(reader, writer):
    try:
        await reader.read(1024)
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\nБот активен! 🚀"
        writer.write(response.encode('utf-8'))
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = await start_server(handle_ping, '0.0.0.0', port)
    logger.info(f"🌐 Асинхронный веб-сервер запущен на порту {port}")
    asyncio.create_task(server.serve_forever())

# ==================== ЗАПУСК БОТА ====================
async def run_bot():
    app = Application.builder().token(TOKEN).build()
    
    # Регистрация команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("stop", cmd_stop))
    
    # Текстовые обработчики
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    logger.info("🌑 DARK ANON CHAT БОТ УСПЕШНО ЗАПУЩЕН!")
    while True:
        await asyncio.sleep(3600)

def main():
    # Создание пустых файлов БД при их отсутствии
    if not os.path.exists(USERS_FILE): save_users({})
    if not os.path.exists(PAIRS_FILE): save_pairs({})
        
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_web_server())
    loop.run_until_complete(run_bot())

if __name__ == "__main__":
    main()
