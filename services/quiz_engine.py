"""
Quiz Engine: Handles the entire lifecycle of a running quiz session.
Sends polls, tracks timers, handles answers, moves to next question, ends quiz.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from aiogram import Bot
from aiogram.types import Message

from models import QuizSession, Quiz, QuizQuestion
from models.session import SessionStatus
from services import (
    update_session, end_session, pause_session, resume_session,
    mark_missed_question, update_leaderboard, get_session,
    get_active_session_by_chat,
)
from services.quiz_service import get_quiz, increment_play_count
from services.user_service import update_user_stats
from keyboards.quiz_keyboards import pause_quiz_kb, get_result_pdf_kb
from utils.helpers import build_leaderboard_text, format_duration, get_rank_emoji, get_quiz_share_link

logger = logging.getLogger(__name__)

# Global timer tasks: {session_id: asyncio.Task}
_timer_tasks: Dict[str, asyncio.Task] = {}


async def send_question(bot: Bot, session: QuizSession, quiz: Quiz, question_index: int):
    """Send a quiz poll for the given question index."""
    if question_index >= len(session.question_order):
        await finalize_quiz(bot, session, quiz)
        return

    question_id = session.question_order[question_index]
    question = next((q for q in quiz.questions if q.question_id == question_id), None)
    if not question:
        logger.error(f"Question {question_id} not found in quiz {quiz.quiz_id}")
        await finalize_quiz(bot, session, quiz)
        return

    session.current_question_index = question_index
    session.answered_this_round = []
    session.question_start_time = datetime.utcnow()
    session.status = SessionStatus.ACTIVE

    # Shuffle options if setting enabled
    if quiz.settings.get("shuffle_options"):
        display_options = question.shuffled_options()
    else:
        display_options = question.options

    # Find correct answer index in possibly shuffled list
    correct_index = next(
        (i for i, o in enumerate(display_options) if o.is_correct), 0
    )

    option_texts = [o.text for o in display_options]
    total = len(session.question_order)
    q_num = question_index + 1

    header = (
        f"📝 <b>Question {q_num}/{total}</b>\n"
        f"⏱ Timer: {question.timer}s\n"
    )
    if quiz.settings.get("exam_mode"):
        header += "🔒 <i>Exam Mode: Results shown at end</i>\n"

    try:
        # Send header message
        await bot.send_message(
            chat_id=session.chat_id,
            text=header,
            parse_mode="HTML",
        )

        # Send native Telegram quiz poll
        poll_msg = await bot.send_poll(
            chat_id=session.chat_id,
            question=question.text[:255],
            options=option_texts,
            type="quiz",
            correct_option_id=correct_index,
            explanation=question.explanation[:200] if question.explanation else None,
            is_anonymous=False,
            open_period=question.timer,
            protect_content=False,
        )

        session.current_poll_message_id = poll_msg.message_id
        session.current_poll_id = poll_msg.poll.id

        # Store shuffled correct index for answer tracking
        session_data = session.to_dict()
        session_data["current_correct_option"] = correct_index
        session_data["current_question_id"] = question_id
        session_data["current_options_map"] = [
            {"text": o.text, "is_correct": o.is_correct} for o in display_options
        ]

        await update_session(session)

        # Schedule auto-advance after timer
        await _schedule_next_question(bot, session, quiz, question)

    except Exception as e:
        logger.error(f"Error sending question: {e}")


async def _schedule_next_question(bot: Bot, session: QuizSession, quiz: Quiz, question: QuizQuestion):
    """Schedule moving to the next question after the timer expires."""
    session_id = session.session_id

    # Cancel existing timer if any
    if session_id in _timer_tasks:
        _timer_tasks[session_id].cancel()

    async def timer_task():
        await asyncio.sleep(question.timer + 1)  # +1 buffer after poll closes

        # Reload session from DB to get latest state
        fresh_session = await get_session(session_id)
        if not fresh_session:
            return
        if fresh_session.status not in (SessionStatus.ACTIVE,):
            return

        fresh_quiz = await get_quiz(fresh_session.quiz_id)
        if not fresh_quiz:
            return

        # Check if anyone answered this round
        if not fresh_session.answered_this_round:
            # Auto-pause
            await pause_session(session_id)
            fresh_session.status = SessionStatus.PAUSED

            try:
                await bot.send_message(
                    chat_id=fresh_session.chat_id,
                    text=(
                        "⏸ <b>Quiz Paused</b>\n\n"
                        "No responses were received in the last question.\n"
                        "The quiz has been automatically paused."
                    ),
                    parse_mode="HTML",
                    reply_markup=pause_quiz_kb(session_id),
                )
            except Exception as e:
                logger.error(f"Error sending pause message: {e}")
            return

        # Mark missed for those who didn't answer
        q_id = fresh_session.question_order[fresh_session.current_question_index]
        await mark_missed_question(fresh_session, q_id)

        # Show live leaderboard if not exam mode
        if not fresh_quiz.settings.get("exam_mode") and fresh_session.participants:
            sorted_p = fresh_session.get_sorted_participants()
            lb_text = build_leaderboard_text(sorted_p, fresh_quiz.title, fresh_session.current_question_index + 1)
            try:
                await bot.send_message(
                    chat_id=fresh_session.chat_id,
                    text=lb_text,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Error sending leaderboard: {e}")

        await update_session(fresh_session)

        # Move to next question
        next_index = fresh_session.current_question_index + 1
        if next_index >= fresh_session.total_questions:
            await finalize_quiz(bot, fresh_session, fresh_quiz)
        else:
            await send_question(bot, fresh_session, fresh_quiz, next_index)

    task = asyncio.create_task(timer_task())
    _timer_tasks[session_id] = task


async def finalize_quiz(bot: Bot, session: QuizSession, quiz: Quiz):
    """End the quiz and send final results."""
    session_id = session.session_id

    # Cancel timer
    if session_id in _timer_tasks:
        _timer_tasks[session_id].cancel()
        del _timer_tasks[session_id]

    # Mark last question missed for non-answerers
    if session.question_order and session.current_question_index < len(session.question_order):
        q_id = session.question_order[session.current_question_index]
        await mark_missed_question(session, q_id)

    await end_session(session_id)
    await update_leaderboard(session, quiz.quiz_id)
    await increment_play_count(quiz.quiz_id)

    total_q = session.total_questions
    max_score = quiz.settings.get("correct_score", 4) * total_q

    # Update user stats for all participants
    for uid, participant in session.participants.items():
        percentage = (participant.correct / total_q * 100) if total_q > 0 else 0
        await update_user_stats(
            uid, participant.correct, participant.wrong, participant.missed,
            participant.score, percentage,
        )

    # Send final summary
    sorted_p = session.get_sorted_participants()
    duration = (datetime.utcnow() - session.started_at).total_seconds()

    summary_lines = [
        f"🏁 <b>Quiz Completed!</b>",
        f"📝 <b>{quiz.title}</b>",
        f"⏱ Duration: {format_duration(duration)}",
        f"👥 Participants: {len(sorted_p)}",
        f"📊 Questions: {total_q}",
        "",
        "🏆 <b>Final Rankings:</b>",
    ]

    for i, p in enumerate(sorted_p[:10]):
        pct = (p.correct / total_q * 100) if total_q > 0 else 0
        rank_emoji = get_rank_emoji(i + 1)
        summary_lines.append(
            f"{rank_emoji} <b>{p.first_name}</b> — "
            f"{p.score:.1f}pts | ✅{p.correct} ❌{p.wrong} ⏭{p.missed} | {pct:.0f}%"
        )

    summary_lines.extend([
        "",
        f"🔗 Play again: {get_quiz_share_link(quiz.quiz_id)}",
    ])

    try:
        await bot.send_message(
            chat_id=session.chat_id,
            text="\n".join(summary_lines),
            parse_mode="HTML",
            reply_markup=get_result_pdf_kb(session_id),
        )
    except Exception as e:
        logger.error(f"Error sending final results: {e}")


async def handle_poll_answer(
    bot: Bot,
    session: QuizSession,
    quiz: Quiz,
    user_id: int,
    username: str,
    first_name: str,
    poll_id: str,
    option_ids: list,
):
    """Handle an answer from a poll. Called from PollAnswer handler."""
    from services.session_service import record_answer

    if session.status != SessionStatus.ACTIVE:
        return
    if session.current_poll_id != poll_id:
        return

    selected_option = option_ids[0] if option_ids else -1
    if selected_option == -1:
        return

    # Get current question's correct option from session
    q_idx = session.current_question_index
    if q_idx >= len(session.question_order):
        return

    q_id = session.question_order[q_idx]
    question = next((q for q in quiz.questions if q.question_id == q_id), None)
    if not question:
        return

    # Determine correct option in possibly shuffled display
    correct_option = session.to_dict().get("current_correct_option", question.correct_option_index)

    now = datetime.utcnow()
    time_taken = (now - session.question_start_time).total_seconds() if session.question_start_time else 0

    result = await record_answer(
        session=session,
        user_id=user_id,
        username=username,
        first_name=first_name,
        question_id=q_id,
        selected_option=selected_option,
        correct_option=correct_option,
        time_taken=time_taken,
        correct_score=quiz.settings.get("correct_score", 4),
        wrong_penalty=quiz.settings.get("wrong_penalty", -1),
        negative_marking=quiz.settings.get("negative_marking", True),
    )

    await update_session(session)

    # In non-exam mode, send feedback (private chat only to avoid spam)
    if not quiz.settings.get("exam_mode") and session.chat_type == "private":
        if result == "correct":
            feedback = f"✅ Correct! +{quiz.settings.get('correct_score', 4)} pts"
        elif result == "wrong":
            penalty = quiz.settings.get("wrong_penalty", -1)
            feedback = f"❌ Wrong! {penalty} pts"
            if question.explanation:
                feedback += f"\n💡 {question.explanation}"
        else:
            return

        try:
            await bot.send_message(chat_id=session.chat_id, text=feedback)
        except Exception as e:
            logger.error(f"Feedback error: {e}")


async def resume_quiz(bot: Bot, session_id: str):
    """Resume a paused quiz."""
    session = await get_session(session_id)
    if not session or session.status != SessionStatus.PAUSED:
        return False

    quiz = await get_quiz(session.quiz_id)
    if not quiz:
        return False

    await resume_session(session_id)
    session.status = SessionStatus.ACTIVE

    await bot.send_message(
        chat_id=session.chat_id,
        text="▶️ <b>Quiz Resumed!</b> Next question coming up...",
        parse_mode="HTML",
    )

    await send_question(bot, session, quiz, session.current_question_index)
    return True


async def stop_quiz(bot: Bot, session_id: str):
    """Forcefully stop a quiz."""
    session = await get_session(session_id)
    if not session:
        return False

    quiz = await get_quiz(session.quiz_id)

    # Cancel timer
    if session_id in _timer_tasks:
        _timer_tasks[session_id].cancel()
        del _timer_tasks[session_id]

    if quiz:
        await finalize_quiz(bot, session, quiz)
    else:
        await end_session(session_id)
        await bot.send_message(
            chat_id=session.chat_id,
            text="⏹ Quiz has been stopped.",
        )
    return True


def cancel_timer(session_id: str):
    """Cancel the timer task for a session."""
    if session_id in _timer_tasks:
        _timer_tasks[session_id].cancel()
        del _timer_tasks[session_id]
