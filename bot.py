
import os
import logging
import json
import random
import asyncio  # Используем asyncio вместо threading
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
        ["🔍 Найти собеседника", "⏹ Остановить диалог"],
        ["👤 Мой профиль", "⭐ Премиум"],
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

# ==================== ИГРЫ ====================
def check_win(board, player):
    win_combinations = [
        [0,1,2], [3,4,5], [6,7,8],
        [0,3,6], [1,4,7], [2,5,8],
        [0,4,8], [2,4,6]
    ]
    for combo in win_combinations:
        if all(board[i] == player for i in combo):
            return True
    return False

def get_best_move(board):
    for i in range(9):
        if board[i] == ' ':
            board_copy = board.copy()
            board_copy[i] = 'O'
            if check_win(board_copy, 'O'):
                return i
    for i in range(9):
        if board[i] == ' ':
            board_copy = board.copy()
            board_copy[i] = 'X'
            if check_win(board_copy, 'X'):
                return i
    for i in range(9):
        if board[i] == ' ':
            return i
    return None

# ==================== ОБРАБОТЧИКИ ====================
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
            f"🌑 ДОБРО ПОЖАЛОВАТЬ В DARK ANON CHAT!\n\n"
            f"🔮 Анонимный чат\n"
            f"Здесь вы можете делать ВСЁ!\n\n"
            f"⚠️ Вы сами отвечаете за свои действия!\n\n"
            f"✅ Полная анонимность\n"
            f"✅ Нет запретов\n"
            f"✅ Свобода общения\n\n"
            f"Нажми 🔍 Найти собеседника",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"🌑 С возвращением!",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)
    users = load_users()
    pairs = load_pairs()
    user = users.get(user_id, {})
    
    if user_id in pairs:
        partner_id = pairs[user_id]
        if partner_id in users:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"💬 Новое сообщение\n\n{text}",
                parse_mode="HTML"
            )
            return
    
    if text == "🔍 Найти собеседника":
        available = None
        for uid, u in users.items():
            if uid != user_id and uid not in pairs:
                available = uid
                break
        
        if available:
            pairs[user_id] = available
            pairs[available] = user_id
            save_pairs(pairs)
            await update.message.reply_text("✅ Собеседник найден!")
            await context.bot.send_message(
                chat_id=available,
                text="✅ Собеседник найден!"
            )
        else:
            await update.message.reply_text("🔍 Ищем собеседника...")
    
    elif text == "⏹ Остановить диалог":
        if user_id in pairs:
            partner_id = pairs[user_id]
            del pairs[user_id]
            if partner_id in pairs:
                del pairs[partner_id]
            save_pairs(pairs)
            await update.message.reply_text("⏹ Диалог остановлен")
    
    elif text == "👤 Мой профиль":
        await update.message.reply_text(
            f"👤 Профиль\n\n"
            f"⭐ Премиум: {'Да' if user.get('premium') else 'Нет'}\n"
            f"💎 Звезд: {user.get('stars', 0)}\n"
            f"👥 Рефералов: {user.get('referrals', 0)}",
            parse_mode="HTML"
        )
    
    elif text == "⭐ Премиум":
        await update.message.reply_text(
            f"⭐ Премиум\n\n"
            f"Цена: 50 звезд\n"
            f"Длительность: 7 дней",
            parse_mode="HTML",
            reply_markup=premium_menu()
        )
    
    elif text == "👥 Рефералы":
        await update.message.reply_text(
            f"👥 Рефералы\n\n"
            f"Ваших рефералов: {user.get('referrals', 0)}\n\n"
            f"Ссылка:\n"
            f"https://t.me/{context.bot.username}?start=ref_{user_id}",
            parse_mode="HTML"
        )
    
    elif text == "🎮 Игры":
        await update.message.reply_text(
            "🎮 Выберите игру:",
            reply_markup=games_menu()
        )
    
    elif text == "📞 Поддержка":
        await update.message.reply_text(
            "📞 Поддержка\n\n@WHITEDARON",
            parse_mode="HTML"
        )
    
    elif text == "ℹ️ О чате":
        await update.message.reply_text(
            "🌑 DARK ANON CHAT\n\n"
            "Версия: 3.0.0\n"
            "Полная анонимность\n"
            "Без запретов",
            parse_mode="HTML"
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    
    if user_id in pairs:
        partner_id = pairs[user_id]
        photo = update.message.photo[-1]
        await context.bot.send_photo(
            chat_id=partner_id,
            photo=photo.file_id,
            caption="📸 Новое фото"
        )

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
        
        await query.edit_message_text(
            "❌ Крестики-нолики\nВыберите клетку:",
            reply_markup=tic_tac_toe_board(board, game_id)
        )
    
    elif data.startswith("tic_"):
        parts = data.split("_")
        if len(parts) == 3 and parts[1] != "none":
            pos = int(parts[2])
            if 'tic_board' in context.user_data:
                board = context.user_data['tic_board']
                if board[pos] == ' ':
                    board[pos] = 'X'
                    
                    if check_win(board, 'X'):
                        user['stars'] = user.get('stars', 0) + 10
                        users[user_id] = user
                        save_users(users)
                        await query.edit_message_text(
                            f"🎉 Победа! +10 ⭐",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔄 Снова", callback_data="game_tic")],
                                [InlineKeyboardButton("🔙 Назад", callback_data="back_games")]
                            ])
                        )
                        return
                    
                    bot_move = get_best_move(board)
                    if bot_move is not None:
                        board[bot_move] = 'O'
                        if check_win(board, 'O'):
                            await query.edit_message_text(
                                "😔 Поражение",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("🔄 Снова", callback_data="game_tic")],
                                    [InlineKeyboardButton("🔙 Назад", callback_data="back_games")]
                                ])
                            )
                            return
                    
                    context.user_data['tic_board'] = board
                    await query.edit_message_text(
                        "❌ Ваш ход:",
                        reply_markup=tic_tac_toe_board(board, parts[1])
                    )
    
    elif data == "game_roulette":
        await query.edit_message_text(
            "🎰 Рулетка\nСтавка: 5 ⭐",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔴 Красный", callback_data="roulette_red")],
                [InlineKeyboardButton("⚫️ Черный", callback_data="roulette_black")],
                [InlineKeyboardButton("🟢 Зеленый", callback_data="roulette_green")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_games")]
            ])
        )
    
    elif data.startswith("roulette_"):
        color = data.split("_")[1]
        result = random.randint(0, 36)
        win = False
        
        if result == 0:
            result_color = "green"
            win = color == "green"
        elif result % 2 == 0:
            result_color = "red"
            win = color == "red"
        else:
            result_color = "black"
            win = color == "black"
        
        if win:
            stars = 10
            user['stars'] = user.get('stars', 0) + stars
            result_text = f"🎉 Выиграли {stars} ⭐!"
        else:
            stars = 5
            user['stars'] = user.get('stars', 0) - stars
            result_text = f"😔 Проиграли {stars} ⭐"
        
        users[user_id] = user
        save_users(users)
        
        await query.edit_message_text(
            f"🎰 Результат: {result}\n{result_text}\n⭐ {user['stars']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Снова", callback_data="game_roulette")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_games")]
            ])
        )
    
    elif data == "game_number":
        await query.edit_message_text(
            "🎲 Угадай число (1-10)\nСтавка: 3 ⭐",
            reply_markup=number_keyboard()
        )
    
    elif data.startswith("num_"):
        guess = int(data.split("_")[1])
        number = random.randint(1, 10)
        
        if guess == number:
            user['stars'] = user.get('stars', 0) + 15
            result = f"🎉 Угадали! +15 ⭐"
        else:
            user['stars'] = user.get('stars', 0) - 3
            result = f"😔 Не угадали! Было {number}"
        
        users[user_id] = user
        save_users(users)
        
        await query.edit_message_text(
            f"{result}\n⭐ {user['stars']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Снова", callback_data="game_number")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_games")]
            ])
        )
    
    elif data == "buy_premium":
        if user.get('stars', 0) >= 50:
            user['stars'] = user.get('stars', 0) - 50
            user['premium'] = True
            user['premium_until'] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            users[user_id] = user
            save_users(users)
            await query.edit_message_text("⭐ Премиум активирован на 7 дней!")
        else:
            await query.edit_message_text(f"❌ Нужно 50 ⭐, у вас {user.get('stars', 0)}")
    
    elif data == "vip_referral":
        await query.edit_message_text(
            f"👥 VIP за реферала\n\nПригласите друга:\nhttps://t.me/{context.bot.username}?start=ref_{user_id}"
        )
    
    elif data == "back_games":
        await query.edit_message_text(
            "🎮 Выберите игру:",
            reply_markup=games_menu()
        )
    
    elif data == "back_main":
        await query.edit_message_text(
            "🌑 Главное меню",
            reply_markup=get_main_keyboard()
        )

# ==================== АСИНХРОННЫЙ ВЕБ-СЕРВЕР ДЛЯ РЕНДЕРА ====================
async def handle_ping(reader, writer):
    """Обрабатывает запросы от Uptime Robot асинхронно"""
    data = await reader.read(1024)
    request = data.decode('utf-8', errors='ignore')
    
    # Формируем HTTP-ответ 200 OK
    response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Connection: close\r\n\r\n"
        "Бот активен! 🚀"
    )
    writer.write(response.encode('utf-8'))
    await writer.drain()
    writer.close()
    await writer.wait_closed()

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = await start_server(handle_ping, '0.0.0.0', port)
    logger.info(f"🌐 Асинхронный веб-сервер запущен на порту {port}")
    # Сервер будет работать в фоне внутри общего event loop-а
    asyncio.create_task(server.serve_forever())

# ==================== ЗАПУСК БОТА ====================
async def run_bot():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Инициализируем и запускаем бота
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    
    logger.info("🌑 DARK ANON CHAT БОТ УСПЕШНО ЗАПУЩЕН!")
    
    # Держим цикл активным бесконечно
    while True:
        await asyncio.sleep(3600)

def main():
    print("🌑 DARK ANON CHAT СТАРТУЕТ...")
    
    # Создаем единый цикл событий для сервера и для бота
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Сначала вешаем веб-сервер в этот же цикл
    loop.run_until_complete(start_web_server())
    
    # Затем запускаем самого бота
    loop.run_until_complete(run_bot())

if __name__ == "__main__":
    main()
