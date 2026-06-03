"""
Quiz creation flow:
1. /create → ask for title
2. Title received → ask to add questions via Telegram Poll
3. User creates a Telegram Quiz Poll → bot detects & saves question
4. Ask to add more or finish
"""
import logging
from aiogram import Router, F, Bot
import json
from aiogram.types import Message, CallbackQuery, Poll
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services import (
    get_or_create_user, create_quiz, get_quiz, update_quiz,
    add_question_to_quiz, delete_question_from_quiz, increment_quiz_created,
    get_user_quizzes,
)
from models import Quiz, QuizQuestion, QuizOption
from keyboards.quiz_keyboards import (
    done_adding_questions_kb, quiz_detail_kb, cancel_kb, quiz_list_kb,
    quiz_settings_kb, confirm_delete_kb, timer_selection_kb, score_selection_kb,
)
from utils.helpers import get_quiz_share_link, escape_html

logger = logging.getLogger(__name__)
router = Router()


class CreateQuizStates(StatesGroup):
    waiting_title = State()
    waiting_question_poll = State()
    editing_title = State()


# ─── /create ──────────────────────────────────────────────────────────────────

@router.message(Command("create"))
@router.callback_query(F.data == "menu_create")
async def cmd_create(event, state: FSMContext):
    is_cb = isinstance(event, CallbackQuery)
    user = event.from_user
    await get_or_create_user(user.id, user.username or "", user.first_name, user.last_name or "")

    msg = (
        "➕ <b>Create a New Quiz</b>\n\n"
        "Send me the <b>title</b> of your quiz.\n\n"
        "<i>Example: General Knowledge Quiz 2024</i>"
    )
    if is_cb:
        await event.answer()
        await event.message.answer(msg, parse_mode="HTML", reply_markup=cancel_kb())
    else:
        await event.answer(msg, parse_mode="HTML", reply_markup=cancel_kb())

    await state.set_state(CreateQuizStates.waiting_title)


@router.message(CreateQuizStates.waiting_title)
async def receive_quiz_title(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", reply_markup=None)
        return

    title = message.text.strip()
    if len(title) < 3:
        await message.answer("⚠️ Title too short. Please enter at least 3 characters.")
        return
    if len(title) > 100:
        await message.answer("⚠️ Title too long. Max 100 characters.")
        return

    user = message.from_user
    quiz = Quiz(
        title=title,
        creator_id=user.id,
        creator_name=user.first_name,
    )
    await create_quiz(quiz)
    await increment_quiz_created(user.id)
    await state.update_data(quiz_id=quiz.quiz_id)
    await state.set_state(CreateQuizStates.waiting_question_poll)

    await message.answer(
        f"✅ Quiz <b>'{escape_html(title)}'</b> created!\n\n"
        "📝 <b>Now add your first question:</b>\n\n"
        "1. Tap the 📎 attachment button\n"
        "2. Select <b>Poll</b>\n"
        "3. Choose <b>Quiz</b> type\n"
        "4. Write your question & options\n"
        "5. Select the correct answer\n"
        "6. Send the poll here!\n\n"
        "<i>I'll automatically detect your quiz poll and save it.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(CreateQuizStates.waiting_question_poll, F.poll)
async def receive_question_poll(message: Message, state: FSMContext):
    """Detect Telegram Quiz Poll sent by user and save as question."""
    poll: Poll = message.poll

    if poll.type != "quiz":
        await message.answer(
            "⚠️ Please send a <b>Quiz</b> type poll (not a regular poll).\n"
            "When creating a poll, select 'Quiz' mode and mark the correct answer.",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    if not quiz_id:
        await state.clear()
        await message.answer("❌ Session expired. Please use /create again.")
        return

    quiz = await get_quiz(quiz_id)
    if not quiz:
        await state.clear()
        await message.answer("❌ Quiz not found. Please use /create again.")
        return

    # Build question from poll
    options = [QuizOption(text=opt.text, is_correct=(i == poll.correct_option_id))
               for i, opt in enumerate(poll.options)]

    question = QuizQuestion(
        text=poll.question,
        options=options,
        explanation=poll.explanation or "",
        timer=quiz.settings.get("default_timer", 30),
    )

    await add_question_to_quiz(quiz_id, question)

    # Reload quiz to get updated count
    quiz = await get_quiz(quiz_id)
    q_count = len(quiz.questions)

    correct_text = next((o.text for o in options if o.is_correct), "Unknown")

    await message.answer(
        f"✅ <b>Question {q_count} saved!</b>\n\n"
        f"📌 <b>Q:</b> {escape_html(poll.question)}\n"
        f"✅ <b>Correct Answer:</b> {escape_html(correct_text)}\n\n"
        f"📊 Total questions: {q_count}\n\n"
        "Add another question or finish:",
        parse_mode="HTML",
        reply_markup=done_adding_questions_kb(quiz_id),
    )


@router.message(CreateQuizStates.waiting_question_poll)
async def waiting_poll_other_message(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        data = await state.get_data()
        quiz_id = data.get("quiz_id")
        await state.clear()
        if quiz_id:
            quiz = await get_quiz(quiz_id)
            if quiz:
                await message.answer(
                    f"✅ Quiz saved with {len(quiz.questions)} questions.",
                    reply_markup=None,
                )
                await message.answer(
                    f"📝 <b>{escape_html(quiz.title)}</b>",
                    parse_mode="HTML",
                    reply_markup=quiz_detail_kb(quiz),
                )
                return
        await message.answer("❌ Cancelled.", reply_markup=None)
        return

    await message.answer(
        "📎 Please send a <b>Quiz Poll</b> to add a question.\n\n"
        "Tap the 📎 attachment icon → Poll → Quiz type",
        parse_mode="HTML",
    )


# ─── Web App Quiz Creation ─────────────────────────────────────────────────────

@router.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        title = data.get("title")
        questions_data = data.get("questions", [])

        if not title or not questions_data:
            await message.answer("⚠️ Received invalid data from Web App.")
            return

        user = message.from_user

        # Create Quiz
        quiz = Quiz(
            title=title,
            creator_id=user.id,
            creator_name=user.first_name,
        )
        await create_quiz(quiz)
        await increment_quiz_created(user.id)

        # Add questions
        for q_data in questions_data:
            options = [
                QuizOption(text=opt["text"], is_correct=opt["is_correct"])
                for opt in q_data["options"]
            ]
            question = QuizQuestion(
                text=q_data["text"],
                options=options,
                explanation=q_data.get("explanation", ""),
                timer=quiz.settings.get("default_timer", 30),
            )
            await add_question_to_quiz(quiz.quiz_id, question)

        # Reload quiz to get updated state
        quiz = await get_quiz(quiz.quiz_id)

        share_link = get_quiz_share_link(quiz.quiz_id)
        await message.answer(
            f"🎉 <b>Quiz Created via Web App!</b>\n\n"
            f"📝 <b>{escape_html(quiz.title)}</b>\n"
            f"❓ Questions: {len(quiz.questions)}\n\n"
            f"🔗 <b>Share Link:</b>\n<code>{share_link}</code>\n\n"
            "Anyone with this link can start your quiz!",
            parse_mode="HTML",
            reply_markup=quiz_detail_kb(quiz),
        )
    except Exception as e:
        logger.error(f"Error handling WebApp data: {e}")
        await message.answer("❌ Failed to process the Web App data.")


# ─── Done adding questions ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_done_adding:"))
async def cb_done_adding(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)

    await state.clear()

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return

    if not quiz.questions:
        await callback.message.answer(
            "⚠️ Your quiz has no questions yet. Please add at least one question.",
            reply_markup=done_adding_questions_kb(quiz_id),
        )
        return

    share_link = get_quiz_share_link(quiz_id)
    await callback.message.answer(
        f"🎉 <b>Quiz Ready!</b>\n\n"
        f"📝 <b>{escape_html(quiz.title)}</b>\n"
        f"❓ Questions: {len(quiz.questions)}\n\n"
        f"🔗 <b>Share Link:</b>\n<code>{share_link}</code>\n\n"
        "Anyone with this link can start your quiz!",
        parse_mode="HTML",
        reply_markup=quiz_detail_kb(quiz),
    )


# ─── Add question to existing quiz ────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_addq:"))
async def cb_add_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return
    if quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Only the quiz creator can add questions.", show_alert=True)
        return

    await state.update_data(quiz_id=quiz_id)
    await state.set_state(CreateQuizStates.waiting_question_poll)

    await callback.message.answer(
        f"📝 <b>Adding question to '{escape_html(quiz.title)}'</b>\n\n"
        "Send me a <b>Quiz Poll</b> to add as a question:\n\n"
        "1. Tap 📎 attachment button\n"
        "2. Select <b>Poll</b> → <b>Quiz</b> type\n"
        "3. Fill in question, options & correct answer\n"
        "4. Send the poll here!",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


# ─── /quizzes ─────────────────────────────────────────────────────────────────

@router.message(Command("quizzes"))
@router.callback_query(F.data == "menu_quizzes")
async def cmd_quizzes(event, state: FSMContext):
    is_cb = isinstance(event, CallbackQuery)
    user = event.from_user

    quizzes = await get_user_quizzes(user.id)

    if not quizzes:
        msg = (
            "📚 <b>My Quizzes</b>\n\n"
            "You haven't created any quizzes yet.\n"
            "Use /create to make your first quiz!"
        )
        kb = None
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="➕ Create Quiz", callback_data="menu_create"))
        kb = builder.as_markup()
        if is_cb:
            await event.answer()
            await event.message.answer(msg, parse_mode="HTML", reply_markup=kb)
        else:
            await event.answer(msg, parse_mode="HTML", reply_markup=kb)
        return

    msg = f"📚 <b>My Quizzes</b> ({len(quizzes)} total)"
    if is_cb:
        await event.answer()
        await event.message.answer(msg, parse_mode="HTML", reply_markup=quiz_list_kb(quizzes))
    else:
        await event.answer(msg, parse_mode="HTML", reply_markup=quiz_list_kb(quizzes))


@router.callback_query(F.data.startswith("quiz_list_page:"))
async def cb_quiz_list_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    quizzes = await get_user_quizzes(callback.from_user.id)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=quiz_list_kb(quizzes, page=page))


# ─── View quiz detail ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_view:"))
async def cb_quiz_view(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return

    is_creator = quiz.creator_id == callback.from_user.id
    q_count = len(quiz.questions)
    settings = quiz.settings

    detail_text = (
        f"📝 <b>{escape_html(quiz.title)}</b>\n\n"
        f"❓ Questions: {q_count}\n"
        f"🎮 Played: {quiz.play_count} times\n\n"
        f"⚙️ <b>Settings:</b>\n"
        f"⏱ Timer: {settings.get('default_timer', 30)}s\n"
        f"✅ Correct: +{settings.get('correct_score', 4)} pts\n"
        f"❌ Wrong: {settings.get('wrong_penalty', -1)} pts\n"
        f"🔀 Shuffle Questions: {'Yes' if settings.get('shuffle_questions') else 'No'}\n"
        f"🔀 Shuffle Options: {'Yes' if settings.get('shuffle_options') else 'No'}\n"
        f"➖ Negative Marking: {'Yes' if settings.get('negative_marking') else 'No'}\n"
        f"🔒 Exam Mode: {'Yes' if settings.get('exam_mode') else 'No'}\n"
    )

    await callback.message.answer(
        detail_text, parse_mode="HTML",
        reply_markup=quiz_detail_kb(quiz, is_creator),
    )


# ─── Share quiz ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_share:"))
async def cb_share_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return

    share_link = get_quiz_share_link(quiz_id)
    await callback.message.answer(
        f"🔗 <b>Share your quiz!</b>\n\n"
        f"📝 <b>{escape_html(quiz.title)}</b>\n\n"
        f"<code>{share_link}</code>\n\n"
        "Anyone with this link can start the quiz in private chat or any group.",
        parse_mode="HTML",
    )


# ─── Preview quiz ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_preview:"))
async def cb_preview_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return

    if quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Only the creator can preview.", show_alert=True)
        return

    if not quiz.questions:
        await callback.message.answer("⚠️ No questions in this quiz.")
        return

    lines = [f"📋 <b>Preview: {escape_html(quiz.title)}</b>\n"]
    for i, q in enumerate(quiz.questions, 1):
        lines.append(f"<b>Q{i}. {escape_html(q.text)}</b>")
        labels = ["A", "B", "C", "D"]
        for j, opt in enumerate(q.options):
            marker = "✅" if opt.is_correct else "  "
            lines.append(f"  {marker} {labels[j]}. {escape_html(opt.text)}")
        if q.explanation:
            lines.append(f"  💡 <i>{escape_html(q.explanation)}</i>")
        lines.append(f"  ⏱ {q.timer}s")
        lines.append("")

    # Split into chunks if too long
    text = "\n".join(lines)
    for i in range(0, len(text), 4000):
        await callback.message.answer(text[i:i+4000], parse_mode="HTML")


# ─── Delete quiz ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_delete:"))
async def cb_delete_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz or quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Access denied.", show_alert=True)
        return

    await callback.message.answer(
        f"🗑️ <b>Delete Quiz?</b>\n\n"
        f"Are you sure you want to delete <b>'{escape_html(quiz.title)}'</b>?\n"
        "This action cannot be undone.",
        parse_mode="HTML",
        reply_markup=confirm_delete_kb(quiz_id),
    )


@router.callback_query(F.data.startswith("quiz_delete_confirm:"))
async def cb_delete_confirm(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)

    if not quiz or quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Access denied.", show_alert=True)
        return

    from services import delete_quiz
    await delete_quiz(quiz_id)
    await callback.answer("✅ Quiz deleted!")
    await callback.message.edit_text("🗑️ Quiz has been deleted.")


# ─── Duplicate quiz ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_duplicate:"))
async def cb_duplicate_quiz(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz:
        await callback.message.answer("❌ Quiz not found.")
        return
    if quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Only creator can duplicate.", show_alert=True)
        return

    user = callback.from_user
    from services import duplicate_quiz
    new_quiz = await duplicate_quiz(quiz_id, user.id, user.first_name)
    if new_quiz:
        await increment_quiz_created(user.id)
        await callback.message.answer(
            f"📄 <b>Quiz Duplicated!</b>\n\n"
            f"New quiz: <b>'{escape_html(new_quiz.title)}'</b>\n"
            f"Questions: {len(new_quiz.questions)}",
            parse_mode="HTML",
            reply_markup=quiz_detail_kb(new_quiz),
        )
    else:
        await callback.message.answer("❌ Failed to duplicate quiz.")


# ─── Edit title ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_edit_title:"))
async def cb_edit_title(callback: CallbackQuery, state: FSMContext):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz or quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Access denied.", show_alert=True)
        return

    await state.update_data(quiz_id=quiz_id)
    await state.set_state(CreateQuizStates.editing_title)
    await callback.message.answer(
        f"✏️ Send the new title for <b>'{escape_html(quiz.title)}'</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(CreateQuizStates.editing_title)
async def receive_new_title(message: Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", reply_markup=None)
        return

    new_title = message.text.strip()
    if len(new_title) < 3 or len(new_title) > 100:
        await message.answer("⚠️ Title must be 3–100 characters.")
        return

    data = await state.get_data()
    quiz_id = data.get("quiz_id")
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await state.clear()
        await message.answer("❌ Quiz not found.")
        return

    quiz.title = new_title
    await update_quiz(quiz)
    await state.clear()

    await message.answer(
        f"✅ Title updated to <b>'{escape_html(new_title)}'</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await message.answer(
        f"📝 <b>{escape_html(new_title)}</b>",
        parse_mode="HTML",
        reply_markup=quiz_detail_kb(quiz),
    )


# ─── Quiz Settings ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("quiz_settings:"))
async def cb_quiz_settings(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz or quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Access denied.", show_alert=True)
        return

    await callback.message.answer(
        f"⚙️ <b>Settings: {escape_html(quiz.title)}</b>",
        parse_mode="HTML",
        reply_markup=quiz_settings_kb(quiz),
    )


@router.callback_query(F.data.startswith("qs_toggle:"))
async def cb_toggle_setting(callback: CallbackQuery):
    _, key, quiz_id = callback.data.split(":")
    quiz = await get_quiz(quiz_id)
    await callback.answer()

    if not quiz or quiz.creator_id != callback.from_user.id:
        await callback.answer("❌ Access denied.", show_alert=True)
        return

    current = quiz.settings.get(key, False)
    quiz.settings[key] = not current
    await update_quiz(quiz)

    await callback.message.edit_reply_markup(reply_markup=quiz_settings_kb(quiz))


@router.callback_query(F.data.startswith("qs_timer:"))
async def cb_settings_timer(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    await callback.answer()
    if not quiz or quiz.creator_id != callback.from_user.id:
        return
    await callback.message.answer(
        "⏱ Select the default timer for questions:",
        reply_markup=timer_selection_kb(quiz_id),
    )


@router.callback_query(F.data.startswith("set_timer:"))
async def cb_set_timer(callback: CallbackQuery):
    parts = callback.data.split(":")
    quiz_id, timer_val = parts[1], int(parts[2])
    quiz = await get_quiz(quiz_id)
    await callback.answer(f"Timer set to {timer_val}s")

    if not quiz or quiz.creator_id != callback.from_user.id:
        return

    quiz.settings["default_timer"] = timer_val
    # Update all questions with new default timer
    for q in quiz.questions:
        q.timer = timer_val
    await update_quiz(quiz)
    await callback.message.edit_reply_markup(reply_markup=quiz_settings_kb(quiz))


@router.callback_query(F.data.startswith("qs_correct_score:"))
async def cb_settings_correct_score(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    await callback.answer()
    await callback.message.answer(
        "✅ Select points for correct answer:",
        reply_markup=score_selection_kb(quiz_id, "correct"),
    )


@router.callback_query(F.data.startswith("qs_wrong_penalty:"))
async def cb_settings_wrong_penalty(callback: CallbackQuery):
    quiz_id = callback.data.split(":")[1]
    await callback.answer()
    await callback.message.answer(
        "❌ Select penalty for wrong answer:",
        reply_markup=score_selection_kb(quiz_id, "wrong"),
    )


@router.callback_query(F.data.startswith("set_score:"))
async def cb_set_score(callback: CallbackQuery):
    parts = callback.data.split(":")
    quiz_id, score_type, value = parts[1], parts[2], float(parts[3])
    quiz = await get_quiz(quiz_id)
    await callback.answer(f"Set to {value}")

    if not quiz or quiz.creator_id != callback.from_user.id:
        return

    if score_type == "correct":
        quiz.settings["correct_score"] = value
    else:
        quiz.settings["wrong_penalty"] = value
    await update_quiz(quiz)
    await callback.message.answer(
        f"⚙️ <b>Settings updated!</b>",
        parse_mode="HTML",
        reply_markup=quiz_settings_kb(quiz),
    )


# ─── /cancel ──────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Operation cancelled.", reply_markup=None)
    else:
        await message.answer("Nothing to cancel.", reply_markup=None)
