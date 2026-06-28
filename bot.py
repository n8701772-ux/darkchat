
import os
import logging
import json
import random
import time
import asyncio
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============================================
# TOKEN FROM RENDER ENVIRONMENT VARIABLES
# ============================================
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("ERROR: BOT_TOKEN not found in environment variables!")

# ===== SETTINGS =====
USERS_FILE = "dark_users.json"
PAIRS_FILE = "dark_pairs.json"
PREMIUM_PRICE = 50
PREMIUM_DURATION_DAYS = 7

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== DATABASES =====
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

# ===== KEYBOARDS =====
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["🔍 Find partner", "⏹ Stop dialog"],
        ["👤 My profile", "⭐ Premium"],
        ["👥 Referrals", "🎮 Games"],
        ["📞 Support", "ℹ️ About"]
    ], resize_keyboard=True)

def games_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Tic-Tac-Toe", callback_data="game_tic")],
        [InlineKeyboardButton("🎰 Roulette", callback_data="game_roulette")],
        [InlineKeyboardButton("🎲 Guess number", callback_data="game_number")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ])

def premium_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Buy Premium (50 Stars)", callback_data="buy_premium")],
        [InlineKeyboardButton("🎁 VIP for referral", callback_data="vip_referral")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
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
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_games")])
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
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_games")])
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

# ====================================================
# HTTP SERVER FOR KEEP-ALIVE (100% PROTECTION)
# ====================================================
class KeepAliveHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        if self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'PONG! OK')
        elif self.path == '/status':
            users = load_users()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f'Users online: {len(users)}'.encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>DARK ANON CHAT is alive!</h1><p>Bot works 24/7!</p>')
    
    def log_message(self, format, *args):
        pass

def run_web():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    print(f"✅ Web server started on port {port}!")
    server.serve_forever()

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    print("🌐 Keep-alive thread started!")

# ====================================================
# BOT HANDLERS
# ====================================================
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
                text="🎉 New referral! VIP for 6 hours activated!",
                parse_mode="HTML"
            )
    
    if user_id not in users:
        users[user_id] = {
            "name": update.effective_user.first_name,
            "username": update.effective_user.username or "No username",
            "gender": "unknown",
            "premium": False,
            "premium_until": "none",
            "stars": 0,
            "referrals": 0,
            "register_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
        
        await update.message.reply_text(
            f"🌑 WELCOME TO DARK ANON CHAT!\n\n"
            f"🔮 Secret anonymous chat\n"
            f"Here you can do ANYTHING YOU WANT\n\n"
            f"⚠️ WARNING:\n"
            f"You are responsible for your actions!\n\n"
            f"✅ Full anonymity\n"
            f"✅ No restrictions\n"
            f"✅ Free communication\n\n"
            f"🔥 Features:\n"
            f"• Anonymous chat\n"
            f"• Sending photos\n"
            f"• Games\n"
            f"• Premium for 50 Telegram Stars\n"
            f"• Referral program\n\n"
            f"💫 Press 🔍 Find partner to start",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"🌑 Welcome back!",
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
                text=f"💬 New message from anonymous user\n\n{text}",
                parse_mode="HTML"
            )
            return
    
    if text == "🔍 Find partner":
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
            
            await update.message.reply_text("✅ Partner found!")
            await context.bot.send_message(
                chat_id=available,
                text="✅ Partner found!"
            )
        else:
            await update.message.reply_text(
                "🔍 Looking for partner...\nNobody is online yet."
            )
    
    elif text == "⏹ Stop dialog":
        if user_id in pairs:
            partner_id = pairs[user_id]
            del pairs[user_id]
            if partner_id in pairs:
                del pairs[partner_id]
            save_pairs(pairs)
            await update.message.reply_text("⏹ Dialog stopped")
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text="⏹ Partner left the chat"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ No active dialog")
    
    elif text == "👤 My profile":
        premium_status = "❌ No"
        if user.get('premium', False):
            until = user.get('premium_until', 'none')
            if until != 'none':
                premium_status = f"✅ Until {until}"
        
        await update.message.reply_text(
            f"👤 Your profile\n\n"
            f"⭐ Premium: {premium_status}\n"
            f"💎 Stars: {user.get('stars', 0)}\n"
            f"👥 Referrals: {user.get('referrals', 0)}",
            parse_mode="HTML"
        )
    
    elif text == "⭐ Premium":
        await update.message.reply_text(
            f"⭐ DARK ANON CHAT Premium\n\n"
            f"Price: 50 Telegram Stars\n"
            f"Duration: 7 days\n\n"
            f"Benefits:\n"
            f"• Gender search\n"
            f"• Priority search\n"
            f"• Double bonuses",
            parse_mode="HTML",
            reply_markup=premium_menu()
        )
    
    elif text == "👥 Referrals":
        await update.message.reply_text(
            f"👥 Referrals\n\n"
            f"Your referrals: {user.get('referrals', 0)}\n\n"
            f"🔗 Your link:\n"
            f"https://t.me/{context.bot.username}?start=ref_{user_id}",
            parse_mode="HTML"
        )
    
    elif text == "🎮 Games":
        await update.message.reply_text(
            "🎮 Choose game:",
            reply_markup=games_menu()
        )
    
    elif text == "📞 Support":
        await update.message.reply_text(
            "📞 Support\n\n@WHITEDARON",
            parse_mode="HTML"
        )
    
    elif text == "ℹ️ About":
        await update.message.reply_text(
            "🌑 DARK ANON CHAT\n\n"
            "Version: 3.0.0\n"
            "Full anonymity\n"
            "No restrictions\n"
            "Responsibility on you",
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
            caption="📸 New photo from anonymous user"
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
            "❌ Tic-Tac-Toe\nChoose cell:",
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
                            f"🎉 You won! +{bonus} ⭐",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔄 Again", callback_data="game_tic")],
                                [InlineKeyboardButton("🔙 Back", callback_data="back_games")]
                            ])
                        )
                        return
                    
                    bot_move = get_best_move(board)
                    if bot_move is not None:
                        board[bot_move] = 'O'
                        if check_win(board, 'O'):
                            await query.edit_message_text(
                                "😔 You lost",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("🔄 Again", callback_data="game_tic")],
                                    [InlineKeyboardButton("🔙 Back", callback_data="back_games")]
                                ])
                            )
                            return
                    
                    context.user_data['tic_board'] = board
                    await query.edit_message_text(
                        "❌ Your turn:",
                        reply_markup=tic_tac_toe_board(board, parts[1])
                    )
    
    elif data == "game_roulette":
        await query.edit_message_text(
            "🎰 Roulette\nBet: 5 ⭐\nChoose color:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔴 Red", callback_data="roulette_red")],
                [InlineKeyboardButton("⚫️ Black", callback_data="roulette_black")],
                [InlineKeyboardButton("🟢 Green", callback_data="roulette_green")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_games")]
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
            result_text = f"🎉 You won {stars} ⭐!"
        else:
            stars = 5
            user['stars'] = user.get('stars', 0) - stars
            result_text = f"😔 You lost {stars} ⭐"
        
        users[user_id] = user
        save_users(users)
        
        await query.edit_message_text(
            f"🎰 Result: {result}\n{result_text}\n⭐ {user['stars']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Again", callback_data="game_roulette")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_games")]
            ])
        )
    
    elif data == "game_number":
        await query.edit_message_text(
            "🎲 Guess number (1-10)\nBet: 3 ⭐",
            reply_markup=number_keyboard()
        )
    
    elif data.startswith("num_"):
        guess = int(data.split("_")[1])
        number = random.randint(1, 10)
        
        if guess == number:
            user['stars'] = user.get('stars', 0) + 15
            result = f"🎉 Guessed! +15 ⭐"
        else:
            user['stars'] = user.get('stars', 0) - 3
            result = f"😔 Not guessed! It was {number}"
        
        users[user_id] = user
        save_users(users)
        
        await query.edit_message_text(
            f"{result}\n⭐ {user['stars']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Again", callback_data="game_number")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_games")]
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
                f"⭐ Premium activated!\nUntil: {user['premium_until']}"
            )
        else:
            await query.edit_message_text(
                f"❌ Not enough stars!\nNeed: {PREMIUM_PRICE}\nYou have: {user.get('stars', 0)}"
            )
    
    elif data == "vip_referral":
        await query.edit_message_text(
            f"👥 VIP for referral\n\n"
            f"Invite a friend:\n"
            f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        )
    
    elif data == "back_games":
        await query.edit_message_text(
            "🎮 Choose game:",
            reply_markup=games_menu()
        )
    
    elif data == "back_main":
        await query.edit_message_text(
            "🌑 Main menu",
            reply_markup=get_main_keyboard()
        )

# ====================================================
# MAIN
# ====================================================
async def main():
    print("🌑 DARK ANON CHAT started!")
    print("⭐ Bot is working!")
    
    keep_alive()
    print("✅ HTTP server started! Bot will NOT sleep!")

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
