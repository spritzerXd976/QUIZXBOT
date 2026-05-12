import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from services import get_or_create_user, get_user
from database import get_db
from config import Collections
from utils.helpers import format_duration, escape_html

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("profile"))
@router.callback_query(F.data == "menu_profile")
async def cmd_profile(event):
    is_cb = isinstance(event, CallbackQuery)
    user_tg = event.from_user

    user = await get_or_create_user(
        user_tg.id, user_tg.username or "", user_tg.first_name, user_tg.last_name or ""
    )

    total_answered = user.total_correct + user.total_wrong
    accuracy = (user.total_correct / total_answered * 100) if total_answered > 0 else 0

    profile_text = (
        f"👤 <b>Profile</b>\n\n"
        f"<b>Name:</b> {escape_html(user.full_name)}\n"
    )
    if user.username:
        profile_text += f"<b>Username:</b> @{user.username}\n"

    profile_text += (
        f"\n📊 <b>Statistics:</b>\n"
        f"🎮 Quizzes Taken: {user.total_quizzes_taken}\n"
        f"➕ Quizzes Created: {user.total_quizzes_created}\n"
        f"✅ Total Correct: {user.total_correct}\n"
        f"❌ Total Wrong: {user.total_wrong}\n"
        f"⏭ Total Missed: {user.total_missed}\n"
        f"🎯 Total Score: {user.total_score:.1f} pts\n"
        f"📈 Best Percentage: {user.best_percentage:.1f}%\n"
        f"🎯 Overall Accuracy: {accuracy:.1f}%\n"
        f"\n📅 Member since: {user.joined_at.strftime('%d %b %Y') if user.joined_at else 'N/A'}"
    )

    if is_cb:
        await event.answer()
        await event.message.answer(profile_text, parse_mode="HTML")
    else:
        await event.answer(profile_text, parse_mode="HTML")


@router.message(Command("leaderboard"))
@router.callback_query(F.data == "menu_leaderboard")
async def cmd_leaderboard(event):
    is_cb = isinstance(event, CallbackQuery)
    db = get_db()

    # Global leaderboard by total score
    cursor = db[Collections.USERS].find(
        {"total_quizzes_taken": {"$gt": 0}},
        sort=[("total_score", -1), ("best_percentage", -1)],
        limit=15,
    )
    users = await cursor.to_list(length=15)

    if not users:
        msg = "🏆 <b>Global Leaderboard</b>\n\nNo quiz attempts yet. Be the first!"
    else:
        lines = ["🏆 <b>Global Leaderboard</b>\n"]
        from utils.helpers import get_rank_emoji
        for i, u in enumerate(users):
            rank = get_rank_emoji(i + 1)
            name = u.get("first_name", "Unknown")[:15]
            score = u.get("total_score", 0)
            pct = u.get("best_percentage", 0)
            quizzes = u.get("total_quizzes_taken", 0)
            lines.append(
                f"{rank} <b>{escape_html(name)}</b> — "
                f"{score:.0f}pts | Best: {pct:.0f}% | {quizzes} quiz(zes)"
            )
        msg = "\n".join(lines)

    if is_cb:
        await event.answer()
        await event.message.answer(msg, parse_mode="HTML")
    else:
        await event.answer(msg, parse_mode="HTML")
