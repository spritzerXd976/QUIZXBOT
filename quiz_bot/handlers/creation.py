from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from quiz_bot.database.db import get_db
import uuid
import datetime
from quiz_bot.config import BASE_URL

router = Router()

class CreateQuiz(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_questions = State()

@router.message(Command("create"))
async def start_quiz_creation(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CreateQuiz.waiting_for_title)
    await message.answer("Let's create a new quiz! 📝\n\nPlease enter the **title** for your quiz:")

@router.message(CreateQuiz.waiting_for_title, F.text)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text, questions=[], quiz_id=str(uuid.uuid4()))
    await state.set_state(CreateQuiz.waiting_for_description)
    await message.answer("Great! Now enter a **description** for your quiz.\n(Or type /skip to leave it empty)")

@router.message(CreateQuiz.waiting_for_description, F.text)
async def process_description(message: Message, state: FSMContext):
    description = "" if message.text == "/skip" else message.text
    await state.update_data(description=description)
    await state.set_state(CreateQuiz.waiting_for_questions)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Create Questions (Web)", web_app=WebAppInfo(url=BASE_URL))]
    ])

    await message.answer(
        "Awesome! Now let's add some questions.\n\n"
        "**Instructions:**\n"
        "1. Tap the paperclip 📎 (attachment) icon.\n"
        "2. Select **Poll**.\n"
        "3. Turn on **Quiz Mode**.\n"
        "4. Fill in the question, options, and select the correct answer.\n"
        "5. (Optional) Add an explanation.\n"
        "6. Send the poll to this chat.\n\n"
        "You can also use the web app button below to view these instructions.",
        reply_markup=markup
    )

@router.message(CreateQuiz.waiting_for_questions, F.poll)
async def process_poll_question(message: Message, state: FSMContext):
    poll = message.poll
    if poll.type != "quiz":
        await message.answer("⚠️ Please send a **Quiz** poll, not a regular poll. Make sure 'Quiz Mode' is turned on.")
        return

    data = await state.get_data()
    questions = data.get("questions", [])

    options = [opt.text for opt in poll.options]

    question_data = {
        "question_id": str(uuid.uuid4()),
        "question": poll.question,
        "options": options,
        "correct_option_id": poll.correct_option_id,
        "explanation": poll.explanation,
        "is_anonymous": poll.is_anonymous
    }

    questions.append(question_data)
    await state.update_data(questions=questions)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Finish", callback_data="finish_quiz_creation")
        ]
    ])

    await message.answer(
        f"✅ Question added! (Total: {len(questions)})\n"
        "Send another poll to add more, or click Finish.",
        reply_markup=markup
    )

@router.callback_query(F.data == "finish_quiz_creation")
async def finish_creation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    questions = data.get("questions", [])

    if not questions:
        await callback.answer("You need to add at least one question!", show_alert=True)
        return

    db = await get_db()
    quiz_id = data["quiz_id"]

    quiz_doc = {
        "quiz_id": quiz_id,
        "creator_id": callback.from_user.id,
        "title": data["title"],
        "description": data["description"],
        "created_at": datetime.datetime.utcnow(),
        "status": "published"
    }
    await db.quizzes.insert_one(quiz_doc)

    for idx, q in enumerate(questions):
        q_doc = {
            "quiz_id": quiz_id,
            "order": idx,
            **q
        }
        await db.quiz_questions.insert_one(q_doc)

    await state.clear()

    bot_info = await callback.bot.get_me()
    share_link = f"https://t.me/{bot_info.username}?start=quiz_{quiz_id}"

    await callback.message.edit_text(
        f"🎉 **Quiz Created Successfully!**\n\n"
        f"**Title:** {data['title']}\n"
        f"**Questions:** {len(questions)}\n\n"
        f"Share this link to let others play:\n{share_link}"
    )
