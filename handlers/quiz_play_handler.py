"""
Quiz play handler:
- /start quiz_ID deep link → handled in start_handler
- quiz_start:quiz_id callback → start quiz from quiz detail page
- PollAnswer handler → track responses
- session_resume / session_end callbacks
- /stopquiz command
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, PollAnswer, ChatMemberUpdated
)
from aiogram.filters import Command

from services import (
    get_quiz, get_or_create_user,
    create_session, get_active_session_by_chat, get_session,
    update_session, pause_session, resume_session,
    get_quiz_leaderboard,
)
from services.quiz_engine import (
    send_question, handle_poll_answer, resume_quiz, stop_quiz, finalize_quiz
)
from models import QuizSession
from models.session import SessionStatus
from keyboards.quiz_keyboards import confirm_end_quiz_kb, pause_quiz_kb
from utils.helpers import build_leaderboard_text, get_quiz_share_link, escape_html, is_group_admin

logger = logging.getLogger(__name__)
router = Router()


# ─── Start quiz from detail page ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_start:"))
async def cb_start_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    user = callback.from_user
    bot: Bot = callback.bot

    await get_or_create_user(user.id, user.username or "", user.first_name, user.last_name or "")

    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("❌ Quiz not found.", show_alert=True)
        return
    if not quiz.questions:
        await callback.answer("❌ This quiz has no questions.", show_alert=True)
        return

    # Check if already running in this chat
    existing = await get_active_session_by_chat(callback.message.chat.id)
    if existing:
        await callback.answer("⚠️ A quiz is already running here!", show_alert=True)
        return

    await callback.answer()

    question_order = [q.question_id for q in quiz.get_questions_ordered()]
    session = QuizSession(
        quiz_id=quiz_id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        started_by=user.id,
        started_by_name=user.first_name,
        question_order=question_order,
    )
    await create_session(session)

    settings = quiz.settings
    start_msg = (
        f"🎯 <b>Quiz Starting!</b>\n\n"
        f"📝 <b>{escape_html(quiz.title)}</b>\n"
        f"❓ Questions: {len(quiz.questions)}\n"
        f"⏱ Timer: {settings.get('default_timer', 30)}s/question\n"
        f"✅ Correct: +{settings.get('correct_score', 4)} pts\n"
    )
    if settings.get("negative_marking"):
        start_msg += f"❌ Wrong: {settings.get('wrong_penalty', -1)} pts\n"
    if settings.get("exam_mode"):
        start_msg += "🔒 Exam Mode ON\n"
    start_msg += f"\n👤 Started by: {user.first_name}\n\nGet ready..."

    await callback.message.answer(start_msg, parse_mode="HTML")

    import asyncio
    await asyncio.sleep(2)
    await send_question(bot, session, quiz, 0)


# ─── Poll Answer Handler ───────────────────────────────────────────────────────

@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer, bot: Bot):
    user = poll_answer.user
    option_ids = poll_answer.option_ids

    # Find active session by poll_id — we need to search across sessions
    # Since poll_answer doesn't directly give us session, we search by poll ID
    from database import get_db
    from config import Collections
    db = get_db()

    session_doc = await db[Collections.SESSIONS].find_one({
        "current_poll_id": poll_answer.poll_id,
        "status": SessionStatus.ACTIVE.value,
    })

    if not session_doc:
        return

    from models import QuizSession
    session = QuizSession.from_dict(session_doc)

    quiz = await get_quiz(session.quiz_id)
    if not quiz:
        return

    await handle_poll_answer(
        bot=bot,
        session=session,
        quiz=quiz,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        poll_id=poll_answer.poll_id,
        option_ids=option_ids,
    )


# ─── Resume Quiz ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("session_resume:"))
async def cb_resume_quiz(callback: CallbackQuery):
    session_id = callback.data.split(":")[1]
    session = await get_session(session_id)

    if not session:
        await callback.answer("❌ Session not found.", show_alert=True)
        return

    # Permission check
    user = callback.from_user
    can_resume = await _can_control_quiz(callback, session, user.id)
    if not can_resume:
        await callback.answer("❌ You don't have permission to resume this quiz.", show_alert=True)
        return

    await callback.answer("▶️ Resuming quiz...")
    await resume_quiz(callback.bot, session_id)


# ─── End Quiz ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("session_end:"))
async def cb_end_quiz(callback: CallbackQuery):
    session_id = callback.data.split(":")[1]
    session = await get_session(session_id)

    if not session:
        await callback.answer("❌ Session not found.", show_alert=True)
        return

    user = callback.from_user
    can_end = await _can_end_quiz(callback, session, user.id)
    if not can_end:
        await callback.answer("❌ Only admins or quiz creator can end the quiz.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "⏹ <b>End Quiz?</b>\nAre you sure you want to end the quiz?\nResults will be shown.",
        parse_mode="HTML",
        reply_markup=confirm_end_quiz_kb(session_id),
    )


@router.callback_query(F.data.startswith("session_end_confirm:"))
async def cb_end_confirm(callback: CallbackQuery):
    session_id = callback.data.split(":")[1]
    session = await get_session(session_id)

    if not session:
        await callback.answer("❌ Session not found.", show_alert=True)
        return

    user = callback.from_user
    can_end = await _can_end_quiz(callback, session, user.id)
    if not can_end:
        await callback.answer("❌ Access denied.", show_alert=True)
        return

    await callback.answer("⏹ Ending quiz...")
    await stop_quiz(callback.bot, session_id)


@router.callback_query(F.data.startswith("session_cancel_end:"))
async def cb_cancel_end(callback: CallbackQuery):
    await callback.answer("Cancelled.")
    await callback.message.delete()


# ─── /stopquiz ────────────────────────────────────────────────────────────────

@router.message(Command("stopquiz"))
async def cmd_stopquiz(message: Message):
    session = await get_active_session_by_chat(message.chat.id)
    if not session:
        await message.answer("❌ No active quiz in this chat.")
        return

    user = message.from_user
    can_end = await _can_end_quiz_message(message, session, user.id)
    if not can_end:
        await message.answer("❌ Only admins or the quiz creator can stop the quiz.")
        return

    await message.answer("⏹ Stopping quiz...")
    await stop_quiz(message.bot, session.session_id)


# ─── Leaderboard callbacks ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_leaderboard:"))
async def cb_quiz_leaderboard(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return

    entries = await get_quiz_leaderboard(quiz_id, limit=10)
    if not entries:
        await callback.message.answer(
            f"🏆 <b>Leaderboard: {escape_html(quiz.title)}</b>\n\nNo attempts yet!",
            parse_mode="HTML",
        )
        return

    lines = [f"🏆 <b>Leaderboard: {escape_html(quiz.title)}</b>\n"]
    from utils.helpers import get_rank_emoji
    for i, entry in enumerate(entries):
        rank = get_rank_emoji(i + 1)
        name = entry.get("first_name", "Unknown")[:15]
        score = entry.get("best_score", 0)
        pct = entry.get("best_percentage", 0)
        attempts = entry.get("total_attempts", 1)
        lines.append(
            f"{rank} <b>{escape_html(name)}</b> — {score:.1f}pts | {pct:.0f}% | {attempts} attempt(s)"
        )

    await callback.message.answer("\n".join(lines), parse_mode="HTML")


# ─── PDF Result ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("result_pdf:"))
async def cb_result_pdf(callback: CallbackQuery):
    session_id = callback.data.split(":")[1]
    session = await get_session(session_id)
    await callback.answer("⏳ Generating PDF...")

    if not session:
        await callback.message.answer("❌ Session not found.")
        return

    quiz = await get_quiz(session.quiz_id)
    if not quiz:
        await callback.message.answer("❌ Quiz data not found.")
        return

    user_id = callback.from_user.id
    if user_id not in session.participants:
        await callback.message.answer("❌ You did not participate in this quiz.")
        return

    try:
        from utils.pdf_generator import generate_result_pdf
        import io
        from aiogram.types import BufferedInputFile

        pdf_bytes = generate_result_pdf(session, quiz, user_id)
        file = BufferedInputFile(pdf_bytes, filename=f"quiz_result_{session_id}.pdf")
        await callback.message.answer_document(
            file,
            caption=f"📄 Your result for <b>{escape_html(quiz.title)}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        await callback.message.answer("❌ Failed to generate PDF. Please try again.")


# ─── Permission helpers ────────────────────────────────────────────────────────

async def _can_control_quiz(callback: CallbackQuery, session: QuizSession, user_id: int) -> bool:
    """Anyone in the group can resume a paused quiz."""
    if session.chat_type == "private":
        return user_id == session.started_by
    # In groups, anyone can resume
    return True


async def _can_end_quiz(callback: CallbackQuery, session: QuizSession, user_id: int) -> bool:
    """Only creator or group admin can end quiz."""
    if user_id == session.started_by:
        return True
    if session.chat_type == "private":
        return user_id == session.started_by

    # Check if admin in group
    try:
        member = await callback.bot.get_chat_member(session.chat_id, user_id)
        return is_group_admin(member.status)
    except Exception:
        return False


async def _can_end_quiz_message(message: Message, session: QuizSession, user_id: int) -> bool:
    """Only creator or group admin can end quiz (message version)."""
    if user_id == session.started_by:
        return True
    if session.chat_type == "private":
        return False

    try:
        member = await message.bot.get_chat_member(message.chat.id, user_id)
        return is_group_admin(member.status)
    except Exception:
        return False
