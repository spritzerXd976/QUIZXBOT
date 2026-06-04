from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from quiz_bot.database.db import get_db
import uuid
import datetime

router = Router()

@router.message(Command("quizzes"))
async def list_quizzes(message: Message):
    db = await get_db()
    quizzes = db.quizzes.find({"creator_id": message.from_user.id})

    markup = InlineKeyboardMarkup(inline_keyboard=[])
    count = 0
    async for q in quizzes:
        count += 1
        markup.inline_keyboard.append([
            InlineKeyboardButton(text=q["title"], callback_data=f"manage_quiz_{q['quiz_id']}")
        ])

    if count == 0:
        await message.answer("You haven't created any quizzes yet. Use /create to make one!")
    else:
        await message.answer("Your Quizzes:\nSelect a quiz to manage:", reply_markup=markup)

@router.callback_query(F.data.startswith("manage_quiz_"))
async def manage_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split("_")[-1]
    db = await get_db()
    quiz = await db.quizzes.find_one({"quiz_id": quiz_id})

    if not quiz:
        await callback.answer("Quiz not found.", show_alert=True)
        return

    bot_info = await callback.bot.get_me()
    share_link = f"https://t.me/{bot_info.username}?start=quiz_{quiz_id}"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Preview", callback_data=f"preview_quiz_{quiz_id}")],
        [InlineKeyboardButton(text="🔗 Share Link", callback_data=f"share_quiz_{quiz_id}")],
        [InlineKeyboardButton(text="📄 Duplicate", callback_data=f"dup_quiz_{quiz_id}")],
        [InlineKeyboardButton(text="❌ Delete", callback_data=f"del_quiz_{quiz_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_quizzes")]
    ])

    await callback.message.edit_text(
        f"🛠 **Manage Quiz:** {quiz['title']}\n"
        f"Description: {quiz.get('description', 'None')}\n"
        f"Link: {share_link}",
        reply_markup=markup
    )

@router.callback_query(F.data == "back_to_quizzes")
async def back_to_quizzes(callback: CallbackQuery):
    await list_quizzes(callback.message)
    await callback.message.delete()

@router.callback_query(F.data.startswith("share_quiz_"))
async def share_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split("_")[-1]
    bot_info = await callback.bot.get_me()
    share_link = f"https://t.me/{bot_info.username}?start=quiz_{quiz_id}"
    await callback.answer(f"Link copied! (Well, functionally.)\n{share_link}", show_alert=True)

@router.callback_query(F.data.startswith("del_quiz_"))
async def delete_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split("_")[-1]
    db = await get_db()

    # Confirm deletion
    await db.quizzes.delete_one({"quiz_id": quiz_id})
    await db.quiz_questions.delete_many({"quiz_id": quiz_id})

    await callback.answer("Quiz deleted successfully.", show_alert=True)
    await back_to_quizzes(callback)

@router.callback_query(F.data.startswith("dup_quiz_"))
async def duplicate_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split("_")[-1]
    db = await get_db()

    orig_quiz = await db.quizzes.find_one({"quiz_id": quiz_id})
    if not orig_quiz:
        return

    new_quiz_id = str(uuid.uuid4())
    new_quiz = dict(orig_quiz)
    del new_quiz["_id"]
    new_quiz["quiz_id"] = new_quiz_id
    new_quiz["title"] = f"{orig_quiz['title']} (Copy)"
    new_quiz["created_at"] = datetime.datetime.utcnow()

    await db.quizzes.insert_one(new_quiz)

    questions = db.quiz_questions.find({"quiz_id": quiz_id})
    async for q in questions:
        new_q = dict(q)
        del new_q["_id"]
        new_q["quiz_id"] = new_quiz_id
        new_q["question_id"] = str(uuid.uuid4())
        await db.quiz_questions.insert_one(new_q)

    await callback.answer("Quiz duplicated!", show_alert=True)
    await back_to_quizzes(callback)

@router.callback_query(F.data.startswith("preview_quiz_"))
async def preview_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split("_")[-1]
    db = await get_db()

    questions = db.quiz_questions.find({"quiz_id": quiz_id}).sort("order", 1)

    text = "👁 **Quiz Preview**\n\n"
    count = 0
    async for q in questions:
        count += 1
        text += f"{count}. {q['question']}\n"
        for i, opt in enumerate(q['options']):
            mark = "✅" if i == q['correct_option_id'] else "❌"
            text += f"   {mark} {opt}\n"
        text += "\n"

    if count == 0:
        text = "This quiz has no questions."

    await callback.message.answer(text)
    await callback.answer()
