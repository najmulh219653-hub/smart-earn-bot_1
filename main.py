import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import datetime
import logging

# ⭐ লগিং সেটআপ ⭐
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- ১. আপনার তথ্য দিন (SETTINGS) ---

# BotFather থেকে পাওয়া আপনার টেলিগ্রাম বট টোকেন
TELEGRAM_BOT_TOKEN = "8400259678:AAEitXXzCj4pB3HIj5DhW_eOsCXwonGOolI" 
# আপনার টেলিগ্রাম ইউজার আইডি (অ্যাডমিন আইডি)
ADMIN_USER_ID = 7229488567

# ✅ আপনার Adsterra Smart Link
ADSTERRA_DIRECT_LINK = "https://roughlydispleasureslayer.com/ykawxa7tnr?key=bacb6ca047e4fabf73e54c2eaf85b2a5" 
# টাস্কের জন্য আপনার ল্যান্ডিং পেজ
TASK_LANDING_PAGE = "https://newspaper.42web.io"

# --- ⭐ চ্যানেল সেটিংস ⭐ ---
CHANNEL_USERNAME = "@EarnQuickOfficial"
CHANNEL_INVITE_LINK = "https://t.me/EarnQuickOfficial"
WHATSAPP_LINK = None 

# --- ⭐ পয়েন্ট ও বোনাস সেটিংস ⭐ ---
DAILY_REWARD_POINTS = 10 
REFERRAL_JOIN_BONUS = 50 
REFERRAL_DAILY_COMMISSION = 2
MIN_WITHDRAW_POINTS = 1000 

# --- ২. ডেটা স্টোরেজ (Temporary Storage) ---
# {user_id: {'points': 0, 'last_claim_date': None, 'referrer_id': None, 'username': '...'} }
user_data = {} 

# --- ৩. সাহায্যকারী ফাংশন: চ্যানেল মেম্বারশিপ চেক ---

async def check_channel_member(context: ContextTypes.DEFAULT_TYPE, user_id):
    """ইউজার চ্যানেলে জয়েন করেছে কিনা তা পরীক্ষা করে"""
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"চ্যানেল সদস্যপদ পরীক্ষা করতে সমস্যা: {e}") 
        return False 

async def show_join_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """জয়েন করার শর্ত এবং বাটন দেখায়"""
    join_message = (
        f"⛔ **কাজ শুরু করার জন্য টেলিগ্রাম চ্যানেলে জয়েন করা আবশ্যক!**\n\n"
        f"অনুগ্রহ করে আমাদের অফিশিয়াল টেলিগ্রাম চ্যানেলে জয়েন করুন। জয়েন করার পরেই আপনি বটের মেনু ব্যবহার করতে পারবেন।"
    )
    
    join_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 টেলিগ্রাম চ্যানেলে জয়েন করুন", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton("✅ জয়েন করেছি, আবার দেখুন", callback_data='check_join')]
    ])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(join_message, reply_markup=join_keyboard, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(join_message, reply_markup=join_keyboard, parse_mode=telegram.constants.ParseMode.MARKDOWN)


# --- ৪. কীবোর্ড তৈরি (৪টি ইনকাম ট্র্যাক সহ) ---

def get_main_keyboard(user_id):
    """বটের প্রধান ইনলাইন কীবোর্ড তৈরি করে"""
    current_points = user_data.get(user_id, {}).get('points', 0)
    
    keyboard = [
        # --- ইনকাম ট্র্যাক ---
        [InlineKeyboardButton("💰 দৈনিক বোনাস ক্লেম করুন", callback_data='daily_reward')],
        [InlineKeyboardButton("📰 ট্র্যাক ১: আজকের খবর দেখুন", url=TASK_LANDING_PAGE)],
        [InlineKeyboardButton("🔗 ট্র্যাক ২: অ্যাপ লিঙ্ক দেখুন", url=TASK_LANDING_PAGE)],
        [InlineKeyboardButton("🧠 ট্র্যাক ৩: কুইজ খেলুন", url=TASK_LANDING_PAGE)],
        # --- অ্যাকাউন্ট ও উইথড্রয়াল ---
        [InlineKeyboardButton(f"📊 আমার ব্যালেন্স: {current_points} পয়েন্ট", callback_data='my_account')],
        [InlineKeyboardButton("💸 উইথড্রয়াল রিকোয়েস্ট", callback_data='withdraw_request')],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- ৫. মূল ফাংশন (COMMAND HANDLERS) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start কমান্ড হ্যান্ডেল করে"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    logger.info(f"User {user_id} ({username}) started the bot.")
    
    # --- ⭐ চ্যানেল জয়েনিং শর্ত ---
    is_member = await check_channel_member(context, user_id)
    if not is_member:
        await show_join_prompt(update, context)
        return
    
    # --- রেফারেল হ্যান্ডলিং ---
    referrer_id = None
    if context.args and context.args[0].startswith('ref'):
        try:
            referrer_id = int(context.args[0][3:])
        except ValueError:
            referrer_id = None
            
    # নতুন ইউজার হলে ডেটাবেসে যোগ করা
    if user_id not in user_data:
        user_data[user_id] = {'points': 0, 'last_claim_date': None, 'referrer_id': referrer_id, 'username': username}
        logger.info(f"New user registered: {user_id}")
        
        # রেফারারকে জয়েনিং বোনাস দেওয়া (যদি থাকে)
        if referrer_id and referrer_id in user_data:
            user_data[referrer_id]['points'] += REFERRAL_JOIN_BONUS 
            logger.info(f"Referral bonus {REFERRAL_JOIN_BONUS} added to referrer {referrer_id}")
            try:
                await context.bot.send_message(
                    chat_id=referrer_id, 
                    text=f"🎁 অভিনন্দন! আপনার রেফার করা নতুন ইউজার ({username}) জয়েন করেছেন। আপনি **{REFERRAL_JOIN_BONUS} বোনাস পয়েন্ট** পেয়েছেন।"
                )
            except telegram.error.BadRequest:
                pass 

    welcome_message = (
        f"🎉 স্বাগতম, **{username}**!\n\n"
        "✅ আপনার চ্যানেল জয়েনিং সফল হয়েছে। এখন আপনি কাজ শুরু করতে পারেন।\n"
        "আপনার টেলিগ্রাম আয়ের স্মার্ট চাবিকাঠি এটাই! নিচের মেনু ব্যবহার করে আপনার ইনকাম শুরু করুন।"
    )
    
    reply_markup = get_main_keyboard(user_id)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ইনলাইন বাটনে ক্লিক হ্যান্ডেল করে"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    logger.info(f"User {user_id} pressed button: {query.data}")

    # --- ⭐ চ্যানেল জয়েনিং চেক ---
    is_member = await check_channel_member(context, user_id)
    if not is_member and query.data not in ['check_join', 'start_menu_btn']:
        await show_join_prompt(update, context)
        return

    # --- জয়েন চেক বাটন ---
    if query.data == 'check_join':
        is_member_after_check = await check_channel_member(context, user_id)
        if is_member_after_check:
            logger.info(f"User {user_id} successfully joined channel and proceeded.")
            await start(query, context)
        else:
            await show_join_prompt(update, context)
        return
            
    # --- দৈনিক রিওয়ার্ড ক্লেম ---
    elif query.data == 'daily_reward':
        today = datetime.date.today()
        last_claim = user_data.get(user_id, {}).get('last_claim_date')

        if last_claim and last_claim == today:
            message = "❌ আপনি আজকের রিওয়ার্ড ইতিমধ্যেই ক্লেম করেছেন। আগামীকাল আবার চেষ্টা করুন।"
        else:
            # পয়েন্ট যোগ
            user_data[user_id]['points'] += DAILY_REWARD_POINTS
            user_data[user_id]['last_claim_date'] = today
            logger.info(f"User {user_id} claimed daily reward. New points: {user_data[user_id]['points']}")
            
            # রেফারারকে কমিশন দেওয়া
            referrer_id = user_data[user_id].get('referrer_id')
            if referrer_id and referrer_id in user_data:
                user_data[referrer_id]['points'] += REFERRAL_DAILY_COMMISSION
                logger.info(f"Referrer {referrer_id} received daily commission.")
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id, 
                        text=f"🎁 কমিশন! আপনার রেফার করা ইউজার আজ দৈনিক রিওয়ার্ড ক্লেম করেছেন। আপনি **{REFERRAL_DAILY_COMMISSION} পয়েন্ট** পেলেন।"
                    )
                except telegram.error.BadRequest:
                    pass 

            message = (
                f"✅ সফল! আপনি আজ **{DAILY_REWARD_POINTS} পয়েন্ট** পেলেন।\n"
                f"আয় দ্বিগুণ করতে অন্যান্য ট্র্যাকে কাজ করুন।\n"
                f"আপনার বর্তমান ব্যালেন্স: {user_data[user_id]['points']} পয়েন্ট।"
            )

        await query.edit_message_text(message, reply_markup=get_main_keyboard(user_id), parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    # --- আমার অ্যাকাউন্ট ---
    elif query.data == 'my_account':
        bot_username = context.bot.username if context.bot.username else "Your_Bot_Username"
        referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
        
        current_points = user_data[user_id]['points']

        account_info = (
            "📊 **আমার অ্যাকাউন্ট ও রিফারেল**\n"
            f"পয়েন্ট: **{current_points}**\n"
            f"উইথড্র করার জন্য প্রয়োজন: {MIN_WITHDRAW_POINTS} পয়েন্ট\n\n"
            "🔗 আপনার রিফারেল লিংক: \n"
            f"`{referral_link}`\n\n"
            f"আপনার রেফারেন্সে কেউ জয়েন করলে **{REFERRAL_JOIN_BONUS} পয়েন্ট** এবং সে দৈনিক রিওয়ার্ড ক্লেম করলে আপনি **{REFERRAL_DAILY_COMMISSION} পয়েন্ট** কমিশন পাবেন!"
        )
        
        back_to_main = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 মূল মেনু", callback_data='start_menu_btn')]
        ])
        
        await query.edit_message_text(account_info, reply_markup=back_to_main, parse_mode=telegram.constants.ParseMode.MARKDOWN)

    # --- উইথড্রয়াল ---
    elif query.data == 'withdraw_request':
        current_points = user_data[user_id]['points']
        
        message = ""
        if current_points >= MIN_WITHDRAW_POINTS:
            # ✅ উইথড্রয়াল মেসেজ আপডেট করা হলো
            message = (
                f"💸 **উইথড্রয়াল রিকোয়েস্ট**\n\n"
                f"আপনার পয়েন্ট: {current_points}\n"
                f"অনুগ্রহ করে আপনার **পেমেন্ট পদ্ধতি** (বিকাশ/নগদ/রকেট/অন্যান্য) এবং **আইডি** লিখে মেসেজ করুন। উদাহরণ:\n"
                "`বিকাশ, 01XXXXXXXXX`\n"
                "`নগদ, 01XXXXXXXXX`\n"
                "`রকেট, 01XXXXXXXXX`\n\n"
                "আমাদের অ্যাডমিন আপনার অনুরোধটি দ্রুত রিভিউ করবে।"
            )
        else:
            message = (
                f"❌ দুঃখিত, উইথড্র করার জন্য আপনার কমপক্ষে **{MIN_WITHDRAW_POINTS} পয়েন্ট** প্রয়োজন।\n"
                f"আপনার বর্তমান পয়েন্ট: {current_points}"
            )

        back_to_main = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 মূল মেনু", callback_data='start_menu_btn')]
        ])
        
        await query.edit_message_text(message, reply_markup=back_to_main, parse_mode=telegram.constants.ParseMode.MARKDOWN)

    # --- মেনু বাটন ---
    elif query.data == 'start_menu_btn':
        await start(query, context)


# --- ৬. মেসেজ হ্যান্ডলার (অ্যাডমিন এবং সাধারণ ইউজার) ---

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """সাধারণ মেসেজ এবং অ্যাডমিন কমান্ড হ্যান্ডেল করে"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # --- ⭐ অ্যাডমিন কমান্ড: /addpoints ⭐ ---
    if user_id == ADMIN_USER_ID and text.startswith('/addpoints '):
        try:
            parts = text.split()
            target_id = int(parts[1])
            points = int(parts[2])
            
            if target_id in user_data:
                user_data[target_id]['points'] += points
                logger.info(f"Admin {user_id} added {points} to user {target_id}. New points: {user_data[target_id]['points']}")
                
                await update.message.reply_text(f"✅ সফল! ইউজার {target_id} এর অ্যাকাউন্টে {points} পয়েন্ট যোগ করা হলো। বর্তমান পয়েন্ট: {user_data[target_id]['points']}")
                
                # টার্গেট ইউজারকে নোটিফিকেশন পাঠানো
                await context.bot.send_message(chat_id=target_id, text=f"🎉 অভিনন্দন! অ্যাডমিন আপনার অ্যাকাউন্টে **{points} পয়েন্ট** যোগ করেছেন। আপনার বর্তমান ব্যালেন্স: **{user_data[target_id]['points']}**")
            else:
                await update.message.reply_text("❌ ত্রুটি: টার্গেট ইউজার ID খুঁজে পাওয়া যায়নি।")
                
        except (ValueError, IndexError):
            await update.message.reply_text("❌ অ্যাডমিন কমান্ডের ব্যবহার: /addpoints <ইউজার_আইডি> <পয়েন্ট>")
            
    # --- ⭐ অ্যাডমিন কমান্ড: /checkuser ⭐ ---
    elif user_id == ADMIN_USER_ID and text.startswith('/checkuser '):
        try:
            target_id = int(text.split()[1])
            
            if target_id in user_data:
                u = user_data[target_id]
                info = (
                    f"👤 ইউজার তথ্য ({target_id}):\n"
                    f"নাম: {u.get('username', 'N/A')}\n"
                    f"পয়েন্ট: {u['points']}\n"
                    f"শেষ ক্লেম: {u['last_claim_date']}\n"
                    f"রেফারার ID: {u['referrer_id']}"
                )
                await update.message.reply_text(info)
            else:
                await update.message.reply_text("❌ ত্রুটি: টার্গেট ইউজার ID খুঁজে পাওয়া যায়নি।")
        except (ValueError, IndexError):
            await update.message.reply_text("❌ অ্যাডমিন কমান্ডের ব্যবহার: /checkuser <ইউজার_আইডি>")


    # --- সাধারণ মেসেজ (উইথড্রয়াল রিকোয়েস্ট) ---
    else:
        logger.info(f"Withdrawal request from user {user_id}: {text}")
        # উইথড্রয়াল রিকোয়েস্ট অ্যাডমিনকে ফরোয়ার্ড করার জন্য
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"💸 **নতুন উইথড্রয়াল রিকোয়েস্ট!**\n"
                 f"ইউজার ID: `{user_id}`\n"
                 f"মেসেজ: {text}"
        )

        await update.message.reply_text(
            "আপনার মেসেজটি (সম্ভাব্য উইথড্রয়াল রিকোয়েস্ট) অ্যাডমিনকে পাঠানো হয়েছে। এটি ম্যানুয়ালি দেখা হচ্ছে।\n"
            "অন্যান্য অপশনের জন্য মেনু ব্যবহার করুন:",
            reply_markup=get_main_keyboard(user_id)
        )

# --- ৭. বট চালানো (MAIN EXECUTION) ---

def main() -> None:
    """বট অ্যাপ্লিকেশন শুরু করে"""
    
    logger.info("Starting Smart Earn Bot...") 
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # হ্যান্ডলার
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler)) 

    print("✅ Smart Earn Bot Running... Check console for logs.")
    application.run_polling(poll_interval=1)

if __name__ == '__main__':
    main()
