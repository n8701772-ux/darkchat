
import os
import logging
import json
import random
import time
import asyncio
import threading
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============================================
# ТОКЕН БЕРЕТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ RENDER
# ============================================
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения Render!")

# ===== НАСТРОЙКИ =====
USERS_FILE = "dark_users.json"
PAIRS_FILE = "dark_pairs.json"
PREMIUM_PRICE = 50
PREMIUM_DURATION_DAYS = 7

# ===== ЛОГГИРОВАНИЕ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== БАЗЫ ДАННЫХ =====
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

# ===== КЛАВИАТУРЫ =====
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
    buttons.append([InlineKeyboardButton("🔙 В игры", callback_data="back_games")])
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
    keyboard.append([InlineKeyboardButton("🔙 В игры", callback_data="back_games")])
    return InlineKeyboardMarkup(keyboard)

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

# ===== ФУНКЦИЯ ПИНГА (НЕ ДАЕТ ЗАСНУТЬ) =====
def keep_alive():
    """Простой пинг, чтобы бот не засыпал"""
    while True:
        time.sleep(300)  # Каждые 5 минут
        print(f"🔄 Keep-alive ping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ===== ОБРАБОТЧИКИ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    
    if context.args and context.args[0].startswith("ref_"):
        ref_id = context.args[0][4:]
        if ref_id != user_id and ref_id in users:
            users[ref_id]['referrals'] = users[ref_id].get('referrals', 0) + 1
            users[ref_id]['premium'] = True
            users[ref_id]['premium_until'] = (datetime.now() + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
            save_users(users)
            await context.bot.send_message(
                chat_id=ref_id,
                text="🎉 Новый реферал! VIP на 6 часов активирован!",
                parse_mode="HTML"
            )
    
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
            f"🔮 Секретный анонимный чат\n"
            f"Здесь вы можете делать ВСЕ, ЧТО ЗАХОТИТЕ\n\n"
            f"⚠️ ПРЕДУПРЕЖДЕНИЕ:\n"
            f"Вы сами отвечаете за свои действия!\n\n"
            f"✅ Полная анонимность\n"
            f"✅ Нет запретов\n"
            f"✅ Свобода общения\n\n"
            f"🔥 Особенности:\n"
            f"• Анонимный чат\n"
            f"• Отправка фото\n"
            f"• Игры\n"
            f"• Премиум за 50 Telegram Stars\n"
            f"• Реферальная программа\n\n"
            f"💫 Нажми 🔍 Найти собеседника",
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
                text=f"💬 Новое сообщение от анонимного пользователя\n\n{text}",
                parse_mode="HTML"
            )
            return
    
    if text == "🔍 Найти собеседника":
        available = None
        for uid, u in users.items():
            if uid != user_id and uid not in pairs and u.get('partner') is None:
                if user.get('premium', False) and u.get('premium', False):
                    if user.get('gender') != 'unknown' and user.get('gender') == u.get('gender'):
                        continue
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
            await update.message.reply_text(
                "🔍 Ищем собеседника...\nПока никого нет."
            )
    
    elif text == "⏹ Остановить диалог":
        if user_id in pairs:
            partner_id = pairs[user_id]
            del pairs[user_id]
            if partner_id in pairs:
                del pairs[partner_id]
            save_pairs(pairs)
            await update.message.reply_text("⏹ Диалог остановлен")
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text="⏹ Собеседник покинул чат"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Нет активного диалога")
    
    elif text == "👤 Мой профиль":
        premium_status = "❌ Нет"
        if user.get('premium', False):
            until = user.get('premium_until', 'none')
            if until != 'none':
                premium_status = f"✅ До {until}"
        
        await update.message.reply_text(
            f"👤 Ваш профиль\n\n"
            f"⭐ Премиум: {premium_status}\n"
            f"💎 Звезд: {user.get('stars', 0)}\n"
            f"👥 Рефералов: {user.get('referrals', 0)}",
            parse_mode="HTML"
        )
    
    elif text == "⭐ Премиум":
        await update.message.reply_text(
            f"⭐ Премиум DARK ANON CHAT\n\n"
            f"Цена: 50 Telegram Stars\n"
            f"Длительность: 7 дней\n\n"
            f"Преимущества:\n"
            f"• Поиск по полу\n"
            f"• Приоритетный поиск\n"
            f"• Удвоенные бонусы",
            parse_mode="HTML",
            reply_markup=premium_menu()
        )
    
    elif text == "👥 Рефералы":
        await update.message.reply_text(
            f"👥 Рефералы\n\n"
            f"Ваших рефералов: {user.get('referrals', 0)}\n\n"
            f"🔗 Ваша ссылка:\n"
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
            "Без запретов\n"
            "Ответственность на вас",
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
            caption="📸 Новое фото от анонимного пользователя"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    users = load_users()
    user = users.get(user_id, {})
    data = query.data
    
    if data == "game_tic":
        game_id = f"tic_{user_id}_{int(time.time())}"
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
                        bonus = 10 if user.get('premium', False) else 5
                        user['stars'] = user.get('stars', 0) + bonus
                        users[user_id] = user
                        save_users(users)
                        
                        await query.edit_message_text(
                            f"🎉 Вы победили! +{bonus} ⭐",
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
                                "😔 Вы проиграли",
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
            "🎰 Рулетка\nСтавка: 5 ⭐\nВыберите цвет:",
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
        
        if result == 0:
            result_color = "green"
            win = color == "green"
        elif result % 2 == 0:
            result_color = "red"
            win = color == "red"
        else:
            result_color = "black"
            win = color == "black"
        
        multiplier = 14 if color == "green" else 2
        if win:
            stars = 5 * multiplier
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
        if user.get('stars', 0) >= PREMIUM_PRICE:
            user['stars'] = user.get('stars', 0) - PREMIUM_PRICE
            user['premium'] = True
            user['premium_until'] = (datetime.now() + timedelta(days=PREMIUM_DURATION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            users[user_id] = user
            save_users(users)
            
            await query.edit_message_text(
                f"⭐ Premium активирован!\nДо: {user['premium_until']}"
            )
        else:
            await query.edit_message_text(
                f"❌ Недостаточно звезд!\nНужно: {PREMIUM_PRICE}\nУ вас: {user.get('stars', 0)}"
            )
    
    elif data == "vip_referral":
        await query.edit_message_text(
            f"👥 VIP за реферала\n\n"
            f"Пригласите друга:\n"
            f"https://t.me/{context.bot.username}?start=ref_{user_id}"
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

# ====================================================
# ЗАПУСК БОТА (С ПИНГОМ В ОТДЕЛЬНОМ ПОТОКЕ)
# ====================================================
async def main():
    print("🌑 DARK ANON CHAT запущен!")
    print("⭐ Бот работает!")

    # ЗАПУСКАЕМ ПИНГ В ОТДЕЛЬНОМ ПОТОКЕ
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    print("🔄 Пинг запущен! Бот не заснет!")

    # ЗАПУСКАЕМ БОТА
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Бесконечное ожидание
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
