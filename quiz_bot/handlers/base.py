from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from quiz_bot.database.db import get_db
import datetime

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandStart):
    db = await get_db()

    # Save or update user
    await db.users.update_one(
        {"user_id": message.from_user.id},
        {"$set": {
            "first_name": message.from_user.first_name,
            "username": message.from_user.username,
            "last_active": datetime.datetime.utcnow()
        }},
        upsert=True
    )

    # Check for deep link
    args = command.args
    if args and args.startswith("quiz_"):
        quiz_id = args.replace("quiz_", "")
        # Forward to play handler
        # A simple redirect instruction for now. Real implementation in play handler.
        await message.answer(f"Starting quiz {quiz_id}...")
        from quiz_bot.handlers.play import start_quiz
        await start_quiz(message, quiz_id)
        return

    await message.answer(
        "👋 Welcome to the Telegram MCQ Quiz Bot!\n\n"
        "Here are some commands you can use:\n"
        "/create - Create a new quiz\n"
        "/quizzes - Manage your quizzes\n"
        "/leaderboard - View top scores\n"
        "/profile - View your profile\n"
        "/help - Show this help message"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 **Help & Commands**\n\n"
        "/start - Start the bot\n"
        "/create - Create a new quiz using native Telegram Quiz Polls\n"
        "/quizzes - View, edit, and share your quizzes\n"
        "/leaderboard - Global leaderboard\n"
        "/profile - View your quiz stats\n"
        "/cancel - Cancel current operation\n"
        "/stopquiz - Stop a running quiz"
    )

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("Operation cancelled.")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    db = await get_db()
    user = await db.users.find_one({"user_id": message.from_user.id})
    if not user:
        await message.answer("User profile not found. Send /start first.")
        return

    attempts = await db.attempts.count_documents({"user_id": message.from_user.id})
    created = await db.quizzes.count_documents({"creator_id": message.from_user.id})

    await message.answer(
        f"👤 **Profile: {message.from_user.first_name}**\n"
        f"Quizzes Played: {attempts}\n"
        f"Quizzes Created: {created}"
    )

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    # Simplified leaderboard based on attempts
    db = await get_db()
    pipeline = [
        {"$group": {"_id": "$user_id", "total_score": {"$sum": "$score"}}},
        {"$sort": {"total_score": -1}},
        {"$limit": 10}
    ]
    leaders = []
    async for doc in db.attempts.aggregate(pipeline):
        leaders.append(doc)

    if not leaders:
        await message.answer("No scores recorded yet!")
        return

    text = "🏆 **Global Leaderboard** 🏆\n\n"
    for i, leader in enumerate(leaders, 1):
        user = await db.users.find_one({"user_id": leader["_id"]})
        name = user["first_name"] if user else "Unknown"
        text += f"{i}. {name} - Score: {leader['total_score']}\n"

    await message.answer(text)
