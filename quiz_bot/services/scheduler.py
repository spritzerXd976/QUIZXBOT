from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from quiz_bot.database.db import get_db
import datetime

scheduler = AsyncIOScheduler()

async def auto_pause_quiz(bot: Bot, session_id: str, chat_id: int):
    db = await get_db()
    session = await db.sessions.find_one({"session_id": session_id})

    if not session or session["status"] != "active":
        return

    await db.sessions.update_one({"session_id": session_id}, {"$set": {"status": "paused"}})

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Resume Quiz", callback_data=f"resume_session_{session_id}")],
        [InlineKeyboardButton(text="🛑 End Quiz", callback_data=f"stop_session_{session_id}")]
    ])

    await bot.send_message(
        chat_id,
        "⏸ **Quiz paused due to no responses.**\nPress Resume when you are ready to continue.",
        reply_markup=markup
    )

def schedule_auto_pause(bot: Bot, session_id: str, chat_id: int, seconds: int = 30):
    job_id = f"auto_pause_{session_id}"

    # Remove existing job if any
    cancel_auto_pause(session_id)

    run_date = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    scheduler.add_job(
        auto_pause_quiz,
        'date',
        run_date=run_date,
        args=[bot, session_id, chat_id],
        id=job_id
    )

def cancel_auto_pause(session_id: str):
    job_id = f"auto_pause_{session_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
