import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject

from services import get_or_create_user, get_quiz
from services.quiz_engine import send_question
from services.session_service import get_active_session_by_chat, create_session
from models import QuizSession
from keyboards.quiz_keyboards import main_menu_kb, webapp_kb
from utils.helpers import get_quiz_share_link
from config import BOT_USERNAME

logger = logging.getLogger(__name__)
router = Router()

START_TEXT = """
👋 <b>Welcome to Quiz Bot!</b>

I help you create and take interactive MCQ quizzes using native Telegram polls.

<b>What can I do?</b>
➕ Create custom quizzes with unlimited questions
📝 4 options per question with correct answer
⏱ Timer per question with auto-advance
🔀 Shuffle questions & options
➖ Negative marking support
🔒 Exam mode
📊 Score tracking & leaderboard
📄 PDF result export
👥 Group multiplayer support

<b>Quick Start:</b>
Use /create to make your first quiz!
You can also use /webapp to launch the Web App creation tool.
"""

HELP_TEXT = """
<b>📖 Quiz Bot — Command Reference</b>

<b>General:</b>
/start — Welcome message & main menu
/help — Show this help
/profile — Your stats & profile
/cancel — Cancel current operation

<b>Quiz Management:</b>
/create — Create a new quiz
/webapp — Launch Web App creation tool
/quizzes — View your quizzes
/leaderboard — Global leaderboard

<b>During a Quiz:</b>
/stopquiz — Stop the current quiz (admin only in groups)

<b>Creating Questions:</b>
When you add a question, you'll be sent to a Telegram Poll wizard.
Simply create a quiz poll in the chat — I'll detect it automatically!

<b>Sharing:</b>
After creating a quiz, get a share link:
<code>t.me/{bot_username}?start=quiz_QUIZ_ID</code>

Anyone can start your quiz using that link!

<b>Group Support:</b>
• Anyone with the link can start a quiz in any group
• All group members can participate
• Only admins can end/stop quiz
• Quiz creator can always control their quiz
"""


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user = message.from_user
    await get_or_create_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )

    # Check for deep link: /start quiz_QUIZ_ID
    if command.args and command.args.startswith("quiz_"):
        quiz_id = command.args[5:]
        await handle_quiz_deeplink(message, quiz_id)
        return

    await message.answer(START_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())


@router.message(Command("webapp"))
async def cmd_webapp(message: Message):
    await message.answer(
        "🌐 Click the button below to open the Quiz Creation Web App:",
        reply_markup=webapp_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
    )
    await message.answer(
        HELP_TEXT.format(bot_username=BOT_USERNAME),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu_help")
async def cb_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        HELP_TEXT.format(bot_username=BOT_USERNAME),
        parse_mode="HTML",
    )


async def handle_quiz_deeplink(message: Message, quiz_id: str):
    """Start a quiz from a deep link."""
    from aiogram import Bot
    bot: Bot = message.bot

    quiz = await get_quiz(quiz_id)
    if not quiz:
        await message.answer("❌ Quiz not found. It may have been deleted.")
        return
    if not quiz.questions:
        await message.answer("❌ This quiz has no questions yet.")
        return

    # Check if quiz already running in this chat
    existing = await get_active_session_by_chat(message.chat.id)
    if existing:
        await message.answer(
            "⚠️ A quiz is already running in this chat!\n"
            "Use /stopquiz to end it first."
        )
        return

    user = message.from_user
    question_order = [q.question_id for q in quiz.get_questions_ordered()]

    session = QuizSession(
        quiz_id=quiz_id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        started_by=user.id,
        started_by_name=user.first_name,
        question_order=question_order,
    )

    await create_session(session)

    q_count = len(quiz.questions)
    settings = quiz.settings
    start_msg = (
        f"🎯 <b>Quiz Starting!</b>\n\n"
        f"📝 <b>{quiz.title}</b>\n"
        f"❓ Questions: {q_count}\n"
        f"⏱ Timer: {settings.get('default_timer', 30)}s per question\n"
        f"✅ Correct: +{settings.get('correct_score', 4)} pts\n"
    )
    if settings.get("negative_marking"):
        start_msg += f"❌ Wrong: {settings.get('wrong_penalty', -1)} pts\n"
    if settings.get("shuffle_questions"):
        start_msg += "🔀 Questions shuffled\n"
    if settings.get("exam_mode"):
        start_msg += "🔒 Exam Mode: Results at end\n"
    start_msg += f"\n👤 Started by: {user.first_name}\n\nGet ready! First question coming up..."

    await message.answer(start_msg, parse_mode="HTML")

    import asyncio
    await asyncio.sleep(2)
    await send_question(bot, session, quiz, 0)
