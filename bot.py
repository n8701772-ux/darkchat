
import os
import logging
import json
import random
import asyncio
from asyncio import start_server
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardRemove, LabeledPrice
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
QUEUE_FILE = "dark_queue.json"  # Файл для очереди поиска

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

def load_queue(): return load_json(QUEUE_FILE, [])
def save_queue(queue): save_json(QUEUE_FILE, queue)

# ==================== КЛАВИАТУРЫ ====================
def games_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Крестики-нолики", callback_data="game_tic")],
        [InlineKeyboardButton("🎰 Рулетка", callback_data="game_roulette")],
        [InlineKeyboardButton("🎲 Угадай число", callback_data="game_number")]
    ])

def premium_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Купить Premium за внутренние 50 ⭐", callback_data="buy_premium")],
        [InlineKeyboardButton("💳 Пополнить баланс (Telegram Stars)", callback_data="topup_balance")]
    ])

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ИГР ====================
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

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    
    if user_id not in users:
        users[user_id] = {
            "name": update.effective_user.first_name,
            "username": update.effective_user.username or "Без ника",
            "premium": False,
            "premium_until": "none",
            "stars": 0,
            "referrals": 0,
            "register_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
    
    text = (
        f"🌑 <b>ДОБРО ПОЖАЛОВАТЬ В DARK ANON CHAT!</b>\n\n"
        f"🔮 <i>Анонимный чат без границ.</i>\n\n"
        f"⚡ <b>Команды бота:</b>\n"
        f"/search — Найти собеседника\n"
        f"/stop — Закончить диалог / отменить поиск\n"
        f"/profile — Мой профиль\n"
        f"/premium — Премиум и пополнение баланса\n"
        f"/topup — Купить 50 Telegram Stars\n"
        f"/games — Игры на звезды\n"
        f"/referrals — Реферальная программа\n"
        f"/support — Поддержка\n"
        f"/about — О чате"
    )
    # Убираем старую клавиатуру с кнопками
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    queue = load_queue()
    
    if user_id in pairs:
        await update.message.reply_text("⚠️ Вы уже в диалоге! Сначала завершите его командой /stop")
        return

    if user_id in queue:
        await update.message.reply_text("🔍 Вы уже в очереди поиска. Пожалуйста, подождите...")
        return

    # Очищаем очередь от зависших пользователей (на всякий случай)
    queue = [uid for uid in queue if uid not in pairs]

    if len(queue) > 0:
        # Берем первого человека из очереди
        partner_id = queue.pop(0)
        
        # Защита от дублей
        if partner_id == user_id:
            queue.append(user_id)
            save_queue(queue)
            return

        # Соединяем
        pairs[user_id] = partner_id
        pairs[partner_id] = user_id
        save_pairs(pairs)
        save_queue(queue)
        
        success_msg = "🔮 <b>Собеседник найден! Приятного общения.</b>\nЗакончить диалог: /stop"
        await update.message.reply_text(success_msg, parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=partner_id, text=success_msg, parse_mode="HTML")
        except:
            pass # Если партнер заблокировал бота
    else:
        # Добавляем в очередь
        queue.append(user_id)
        save_queue(queue)
        await update.message.reply_text("🔍 <b>Ищем собеседника...</b>\n\nОстановить поиск: /stop", parse_mode="HTML")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    queue = load_queue()
    stopped = False
    
    if user_id in queue:
        queue.remove(user_id)
        save_queue(queue)
        await update.message.reply_text("⏹ <b>Поиск отменен.</b>\nНайти: /search", parse_mode="HTML")
        stopped = True
        
    if user_id in pairs:
        partner_id = pairs.pop(user_id)
        if partner_id in pairs:
            pairs.pop(partner_id)
        save_pairs(pairs)
        
        await update.message.reply_text("⏹ <b>Вы завершили диалог.</b>\nНайти нового: /search", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=partner_id, text="⏹ <b>Собеседник покинул чат.</b>\nНайти нового: /search", parse_mode="HTML")
        except:
            pass
        stopped = True
        
    if not stopped:
        await update.message.reply_text("❌ Вы сейчас ни с кем не общаетесь и не находитесь в поиске.")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    await update.message.reply_text(
        f"🌌 <b>ТВОЙ DARK ПРОФИЛЬ</b>\n\n"
        f"👑 Премиум: <code>{'Активен ✨' if user.get('premium') else 'Отсутствует ❌'}</code>\n"
        f"💎 Баланс звезд: <code>{user.get('stars', 0)} ⭐</code>\n"
        f"👥 Рефералов: <code>{user.get('referrals', 0)} чел.</code>",
        parse_mode="HTML"
    )

async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⭐ <b>DARK PREMIUM</b>\n\n"
        f"Цена: <b>50 внутренних звезд</b> на 7 дней\n"
        f"Если у вас не хватает баланса, вы можете пополнить его через официальные Telegram Stars.",
        parse_mode="HTML",
        reply_markup=premium_menu()
    )

async def cmd_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    title = "Пополнение баланса (50 ⭐)"
    description = "Покупка внутренних звезд за официальные Telegram Stars"
    payload = "buy_50_stars"
    currency = "XTR" # Код валюты Telegram Stars
    price = 50 # 50 Telegram Stars
    prices = [LabeledPrice("50 Звезд", price)]
    
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="", # Для Telegram Stars токен должен быть пустым
        currency=currency,
        prices=prices
    )

async def cmd_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 <b>Выберите игру:</b>", parse_mode="HTML", reply_markup=games_menu())

async def cmd_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    await update.message.reply_text(
        f"👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"Ваших рефералов: <code>{user.get('referrals', 0)}</code>\n\n"
        f"🔗 <b>Твоя инвайт-ссылка:</b>\n"
        f"<code>https://t.me/{context.bot.username}?start=ref_{user_id}</code>",
        parse_mode="HTML"
    )

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 <b>Поддержка и предложения:</b>\n\n"
        "Пишите в личку разработчику <b>@WHITEDARON</b> ваши идеи, что можно добавить или улучшить в боте!",
        parse_mode="HTML"
    )

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌑 <b>DARK ANON CHAT</b>\n\n• Версия: <code>4.0 Premium</code>\n• Полная анонимность\n• Мгновенный поиск", parse_mode="HTML")

# ==================== ОПЛАТА TELEGRAM STARS ====================
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Подтверждаем, что готовы принять платеж
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    
    # Начисляем 50 звезд
    user['stars'] = user.get('stars', 0) + 50
    users[user_id] = user
    save_users(users)
    
    await update.message.reply_text("🎉 <b>Оплата успешно прошла!</b>\nНа ваш внутренний баланс зачислено 50 ⭐.", parse_mode="HTML")

# ==================== ОБРАБОТКА ТЕКСТА И ФОТО ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    
    if user_id in pairs:
        partner_id = pairs[user_id]
        try:
            await context.bot.send_message(
                chat_id=partner_id,
                text=f"💬 <b>Новое сообщение</b>\n\n{text}",
                parse_mode="HTML"
            )
        except:
            # Если партнер удалил бота, разрываем пару
            await cmd_stop(update, context)
    else:
        await update.message.reply_text("⚠️ <b>Вы не в диалоге!</b> Отправьте /search, чтобы найти собеседника.", parse_mode="HTML")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    pairs = load_pairs()
    
    if user_id in pairs:
        partner_id = pairs[user_id]
        photo = update.message.photo[-1]
        try:
            await context.bot.send_photo(
                chat_id=partner_id,
                photo=photo.file_id,
                caption="📸 <b>Новое фото</b>",
                parse_mode="HTML"
            )
        except:
            await cmd_stop(update, context)
    else:
        await update.message.reply_text("⚠️ Фотографии можно отправлять только во время активного диалога!")

# ==================== ИНЛАЙН КНОПКИ ====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    users = load_users()
    user = users.get(user_id, {})
    data = query.data
    
    if data == "topup_balance":
        # Имитируем команду /topup из кнопки
        title = "Пополнение баланса (50 ⭐)"
        description = "Покупка внутренних звезд за официальные Telegram Stars"
        payload = "buy_50_stars"
        prices = [LabeledPrice("50 Звезд", 50)]
        await context.bot.send_invoice(chat_id=query.message.chat_id, title=title, description=description, payload=payload, provider_token="", currency="XTR", prices=prices)
        
    elif data == "buy_premium":
        if user.get('stars', 0) >= 50:
            user['stars'] -= 50
            user['premium'] = True
            user['premium_until'] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            users[user_id] = user
            save_users(users)
            await query.edit_message_text("⭐ <b>Премиум успешно активирован на 7 дней!</b>", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ <b>Недостаточно средств.</b> Нужно 50 ⭐. У вас: {user.get('stars', 0)} ⭐\nПополните баланс командой /topup", parse_mode="HTML")
            
    elif data == "game_tic":
        game_id = f"tic_{user_id}_{int(datetime.now().timestamp())}"
        board = [' '] * 9
        context.user_data['tic_board'] = board
        context.user_data['tic_game_id'] = game_id
        await query.edit_message_text("❌ <b>Крестики-нолики</b>\nВаш ход:", parse_mode="HTML", reply_markup=tic_tac_toe_board(board, game_id))
    
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
                    await query.edit_message_text(f"🎉 <b>Победа!</b> +10 ⭐\nБаланс: {user['stars']}", parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Играть снова", callback_data="game_tic")],[InlineKeyboardButton("🔙 В игры", callback_data="back_games")]]))
                    return
                
                bot_move = get_best_move(board)
                if bot_move is not None:
                    board[bot_move] = 'O'
                    if check_win(board, 'O'):
                        await query.edit_message_text("😔 <b>Поражение.</b> Бот выиграл.", parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать снова", callback_data="game_tic")],[InlineKeyboardButton("🔙 В игры", callback_data="back_games")]]))
                        return
                
                context.user_data['tic_board'] = board
                await query.edit_message_text("❌ <b>Ваш ход:</b>", parse_mode="HTML", reply_markup=tic_tac_toe_board(board, parts[1]))
                
    elif data == "game_roulette":
        await query.edit_message_text("🎰 <b>Рулетка (Ставка: 5 ⭐)</b>:", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔴 Красный", callback_data="roulette_red")],[InlineKeyboardButton("⚫️ Черный", callback_data="roulette_black")],[InlineKeyboardButton("🟢 Зеленый", callback_data="roulette_green")],[InlineKeyboardButton("🔙 Назад", callback_data="back_games")]]))
    
    elif data.startswith("roulette_"):
        color = data.split("_")[1]
        result = random.randint(0, 36)
        result_color = "green" if result == 0 else ("red" if result % 2 == 0 else "black")
        win = color == result_color
        if win:
            stars = 35 if color == "green" else 10
            user['stars'] = user.get('stars', 0) + stars
            msg = f"🎉 <b>Победа! Выпал {result_color.upper()}. +{stars} ⭐</b>"
        else:
            user['stars'] = max(0, user.get('stars', 0) - 5)
            msg = f"😔 <b>Проигрыш. Выпало {result} ({result_color.upper()}). -5 ⭐</b>"
        users[user_id] = user
        save_users(users)
        await query.edit_message_text(f"{msg}\n💰 Баланс: {user['stars']} ⭐", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Крутить еще", callback_data="game_roulette")],[InlineKeyboardButton("🔙 В игры", callback_data="back_games")]]))
            
    elif data == "game_number":
        buttons = [[InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(r, r+5)] for r in (1, 6)]
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_games")])
        await query.edit_message_text("🎲 <b>Угадай число от 1 до 10 (Ставка: 3 ⭐):</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
        
    elif data.startswith("num_"):
        guess = int(data.split("_")[1])
        number = random.randint(1, 10)
        if guess == number:
            user['stars'] = user.get('stars', 0) + 15
            msg = f"🎉 <b>Угадал! Было {number}. +15 ⭐</b>"
        else:
            user['stars'] = max(0, user.get('stars', 0) - 3)
            msg = f"😔 <b>Мимо. Загадано {number}. -3 ⭐</b>"
        users[user_id] = user
        save_users(users)
        await query.edit_message_text(f"{msg}\n💰 Баланс: {user['stars']} ⭐", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Еще раз", callback_data="game_number")],[InlineKeyboardButton("🔙 В игры", callback_data="back_games")]]))
            
    elif data == "back_games":
        await query.edit_message_text("🎮 <b>Выберите игру:</b>", parse_mode="HTML", reply_markup=games_menu())

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
    
    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("premium", cmd_premium))
    app.add_handler(CommandHandler("topup", cmd_topup))
    app.add_handler(CommandHandler("games", cmd_games))
    app.add_handler(CommandHandler("referrals", cmd_referrals))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("about", cmd_about))
    
    # Текст, фото, кнопки, платежи
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчики для официальных Telegram Stars оплат
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
