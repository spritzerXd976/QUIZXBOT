from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from quiz_bot.database.db import get_db
import uuid
import datetime
import random
import os
from quiz_bot.utils.pdf_export import generate_results_pdf
from quiz_bot.services.scheduler import schedule_auto_pause, cancel_auto_pause

router = Router()

async def start_quiz(message: Message, quiz_id: str):
    db = await get_db()
    quiz = await db.quizzes.find_one({"quiz_id": quiz_id})

    if not quiz:
        await message.answer("Quiz not found.")
        return

    # Fetch questions and shuffle
    questions_cursor = db.quiz_questions.find({"quiz_id": quiz_id})
    questions = []
    async for q in questions_cursor:
        questions.append(q)

    if not questions:
        await message.answer("This quiz has no questions.")
        return

    random.shuffle(questions)

    session_id = str(uuid.uuid4())

    session_doc = {
        "session_id": session_id,
        "quiz_id": quiz_id,
        "chat_id": message.chat.id,
        "creator_id": quiz["creator_id"],
        "questions": questions,
        "current_index": 0,
        "status": "active",
        "started_at": datetime.datetime.utcnow(),
        "participants": {},
        "current_poll_id": None,
        "current_question_id": None
    }
    await db.sessions.insert_one(session_doc)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Stop Quiz", callback_data=f"stop_session_{session_id}")]
    ])

    await message.answer(
        f"🚀 **Starting Quiz:** {quiz['title']}\n"
        f"Questions: {len(questions)}\n"
        f"Get ready!",
        reply_markup=markup
    )

    await send_next_question(message.bot, session_id, message.chat.id)

async def send_next_question(bot: Bot, session_id: str, chat_id: int):
    db = await get_db()
    session = await db.sessions.find_one({"session_id": session_id})

    if not session or session["status"] != "active":
        return

    current_index = session["current_index"]
    questions = session["questions"]

    if current_index >= len(questions):
        await end_quiz(bot, session_id, chat_id)
        return

    q = questions[current_index]

    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"[{current_index+1}/{len(questions)}] {q['question']}",
        options=q['options'],
        type="quiz",
        correct_option_id=q['correct_option_id'],
        explanation=q.get('explanation', ''),
        is_anonymous=False # Must be false to track users
    )

    await db.sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "current_poll_id": poll_msg.poll.id,
            "current_question_id": q["question_id"]
        }}
    )

    # Schedule auto-pause if no answers in 30 seconds
    schedule_auto_pause(bot, session_id, chat_id, 30)


@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, bot: Bot):
    db = await get_db()
    session = await db.sessions.find_one({"current_poll_id": poll_answer.poll_id, "status": "active"})

    if not session:
        return

    cancel_auto_pause(session["session_id"])

    user_id = str(poll_answer.user.id)
    username = poll_answer.user.first_name

    # In MongoDB we want to use $inc to avoid race conditions.
    # But first, we need to ensure the participant structure exists.
    # We can do this with $set for the name, and $inc for the scores.

    # Find the corresponding question
    # We use next() because questions are stored in an array and current_index isn't reliable for grading if updated concurrently
    question = None
    for q in session["questions"]:
        if q["question_id"] == session["current_question_id"]:
            question = q
            break

    if not question:
        return

    is_correct = poll_answer.option_ids[0] == question["correct_option_id"]
    points = 1 if is_correct else -0.25 # Negative marking

    await db.sessions.update_one(
        {"session_id": session["session_id"]},
        {
            "$set": {f"participants.{user_id}.name": username},
            "$inc": {
                f"participants.{user_id}.score": points,
                f"participants.{user_id}.correct": 1 if is_correct else 0,
                f"participants.{user_id}.wrong": 0 if is_correct else 1
            }
        }
    )

    # Logic for multiplayer: The question advancement should be handled via a timer, not by every user's answer.
    # To keep it simple but functional for multiplayer: we will advance the question 10 seconds after the FIRST answer.
    # We use a specific field `advancing_question_id` to ensure only one task waits and advances.

    res = await db.sessions.update_one(
        {"session_id": session["session_id"], "advancing_question_id": {"$ne": session["current_question_id"]}},
        {"$set": {"advancing_question_id": session["current_question_id"]}}
    )

    if res.modified_count > 0:
        import asyncio
        await asyncio.sleep(10) # Wait for other users to answer

        latest_session = await db.sessions.find_one({"session_id": session["session_id"]})
        if latest_session and latest_session["status"] == "active" and latest_session["current_question_id"] == session["current_question_id"]:
            # Increment index safely
            await db.sessions.update_one(
                {"session_id": session["session_id"]},
                {"$inc": {"current_index": 1}}
            )
            await send_next_question(bot, session["session_id"], session["chat_id"])

@router.callback_query(F.data.startswith("stop_session_"))
async def stop_session_btn(callback: CallbackQuery):
    session_id = callback.data.split("_")[-1]
    db = await get_db()
    session = await db.sessions.find_one({"session_id": session_id})

    if not session:
        return

    # Permission check
    if callback.message.chat.type in ["group", "supergroup"]:
        member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
        if member.status not in ["creator", "administrator"] and callback.from_user.id != session["creator_id"]:
            await callback.answer("Only admins or the creator can stop the quiz.", show_alert=True)
            return
    elif callback.from_user.id != session["creator_id"]:
        await callback.answer("Not allowed.", show_alert=True)
        return

    await end_quiz(callback.bot, session_id, callback.message.chat.id)
    await callback.answer()

@router.message(Command("stopquiz"))
async def cmd_stopquiz(message: Message):
    db = await get_db()
    session = await db.sessions.find_one({"chat_id": message.chat.id, "status": "active"})
    if session:
        # Check permissions similarly
        if message.chat.type in ["group", "supergroup"]:
            member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ["creator", "administrator"] and message.from_user.id != session["creator_id"]:
                await message.answer("Only admins or the creator can stop the quiz.")
                return
        await end_quiz(message.bot, session["session_id"], message.chat.id)
    else:
        await message.answer("No active quiz in this chat.")

async def end_quiz(bot: Bot, session_id: str, chat_id: int):
    cancel_auto_pause(session_id)
    db = await get_db()
    await db.sessions.update_one({"session_id": session_id}, {"$set": {"status": "finished", "ended_at": datetime.datetime.utcnow()}})

    session = await db.sessions.find_one({"session_id": session_id})
    participants = session.get("participants", {})

    if not participants:
        await bot.send_message(chat_id, "🛑 Quiz ended. No participants played.")
        return

    # Sort leaderboard
    leaders = sorted(participants.values(), key=lambda x: x["score"], reverse=True)

    text = "🏁 **Quiz Finished! Leaderboard:**\n\n"
    for i, p in enumerate(leaders, 1):
        text += f"{i}. {p['name']} - Score: {p['score']} (✅ {p['correct']} | ❌ {p['wrong']})\n"

    # Save attempt stats for DB
    for uid, p in participants.items():
        await db.attempts.insert_one({
            "user_id": int(uid),
            "quiz_id": session["quiz_id"],
            "session_id": session_id,
            "score": p["score"],
            "correct": p["correct"],
            "wrong": p["wrong"],
            "date": datetime.datetime.utcnow()
        })

    # PDF export
    try:
        pdf_path = f"/tmp/results_{session_id}.pdf"
        generate_results_pdf(leaders, session["quiz_id"], pdf_path)
        from aiogram.types import FSInputFile
        doc = FSInputFile(pdf_path)
        await bot.send_document(chat_id, doc, caption="📊 Final Results PDF")
        os.remove(pdf_path)
    except Exception as e:
        print(f"Error generating PDF: {e}")

    await bot.send_message(chat_id, text)

@router.callback_query(F.data.startswith("resume_session_"))
async def resume_session(callback: CallbackQuery):
    session_id = callback.data.split("_")[-1]
    db = await get_db()

    session = await db.sessions.find_one({"session_id": session_id})
    if not session or session["status"] != "paused":
        await callback.answer("Cannot resume this quiz.", show_alert=True)
        return

    await db.sessions.update_one({"session_id": session_id}, {"$set": {"status": "active"}})
    await callback.message.edit_text("▶️ Quiz Resumed!")

    # Simply send the current question again (or the next one)
    # Re-sending the current index. We need to reset poll id logic
    await send_next_question(callback.bot, session_id, callback.message.chat.id)
    await callback.answer()
