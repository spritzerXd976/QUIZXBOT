from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Optional
from models import Quiz
from config import WEBAPP_URL


def webapp_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🌐 Create via Web App", web_app=WebAppInfo(url=WEBAPP_URL))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Create Quiz", callback_data="menu_create"),
        InlineKeyboardButton(text="📚 My Quizzes", callback_data="menu_quizzes"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="menu_leaderboard"),
        InlineKeyboardButton(text="👤 Profile", callback_data="menu_profile"),
    )
    builder.row(InlineKeyboardButton(text="❓ Help", callback_data="menu_help"))
    return builder.as_markup()


def quiz_list_kb(quizzes: List[Quiz], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = start + per_page
    page_quizzes = quizzes[start:end]

    for quiz in page_quizzes:
        q_count = len(quiz.questions)
        builder.row(
            InlineKeyboardButton(
                text=f"📝 {quiz.title[:30]} ({q_count}Q)",
                callback_data=f"quiz_view:{quiz.quiz_id}",
            )
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"quiz_list_page:{page-1}"))
    if end < len(quizzes):
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"quiz_list_page:{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="➕ Create New Quiz", callback_data="menu_create"))
    return builder.as_markup()


def quiz_detail_kb(quiz: Quiz, is_creator: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="▶️ Start Quiz", callback_data=f"quiz_start:{quiz.quiz_id}"),
        InlineKeyboardButton(text="🔗 Share Link", callback_data=f"quiz_share:{quiz.quiz_id}"),
    )
    if is_creator:
        builder.row(
            InlineKeyboardButton(text="➕ Add Question", callback_data=f"quiz_addq:{quiz.quiz_id}"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data=f"quiz_settings:{quiz.quiz_id}"),
        )
        builder.row(
            InlineKeyboardButton(text="📋 Preview", callback_data=f"quiz_preview:{quiz.quiz_id}"),
            InlineKeyboardButton(text="📄 Duplicate", callback_data=f"quiz_duplicate:{quiz.quiz_id}"),
        )
        builder.row(
            InlineKeyboardButton(text="✏️ Edit Title", callback_data=f"quiz_edit_title:{quiz.quiz_id}"),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"quiz_delete:{quiz.quiz_id}"),
        )
    builder.row(InlineKeyboardButton(text="🏆 Leaderboard", callback_data=f"quiz_leaderboard:{quiz.quiz_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data="menu_quizzes"))
    return builder.as_markup()


def quiz_settings_kb(quiz: Quiz) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    s = quiz.settings
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅' if s.get('shuffle_questions') else '❌'} Shuffle Questions",
            callback_data=f"qs_toggle:shuffle_questions:{quiz.quiz_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅' if s.get('shuffle_options') else '❌'} Shuffle Options",
            callback_data=f"qs_toggle:shuffle_options:{quiz.quiz_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅' if s.get('negative_marking') else '❌'} Negative Marking",
            callback_data=f"qs_toggle:negative_marking:{quiz.quiz_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"{'✅' if s.get('exam_mode') else '❌'} Exam Mode",
            callback_data=f"qs_toggle:exam_mode:{quiz.quiz_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⏱ Timer: {s.get('default_timer', 30)}s",
            callback_data=f"qs_timer:{quiz.quiz_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Score: +{s.get('correct_score', 4)}",
            callback_data=f"qs_correct_score:{quiz.quiz_id}",
        ),
        InlineKeyboardButton(
            text=f"❌ Penalty: {s.get('wrong_penalty', -1)}",
            callback_data=f"qs_wrong_penalty:{quiz.quiz_id}",
        ),
    )
    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data=f"quiz_view:{quiz.quiz_id}"))
    return builder.as_markup()


def pause_quiz_kb(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="▶️ Resume Quiz", callback_data=f"session_resume:{session_id}"),
        InlineKeyboardButton(text="⏹ End Quiz", callback_data=f"session_end:{session_id}"),
    )
    return builder.as_markup()


def confirm_delete_kb(quiz_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"quiz_delete_confirm:{quiz_id}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data=f"quiz_view:{quiz_id}"),
    )
    return builder.as_markup()


def confirm_end_quiz_kb(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yes, End Quiz", callback_data=f"session_end_confirm:{session_id}"),
        InlineKeyboardButton(text="❌ Cancel", callback_data=f"session_cancel_end:{session_id}"),
    )
    return builder.as_markup()


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Cancel"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def done_adding_questions_kb(quiz_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Done Adding Questions", callback_data=f"quiz_done_adding:{quiz_id}"),
        InlineKeyboardButton(text="➕ Add Another", callback_data=f"quiz_addq:{quiz_id}"),
    )
    return builder.as_markup()


def correct_answer_kb(options: List[str], question_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    labels = ["A", "B", "C", "D"]
    for i, opt in enumerate(options):
        builder.row(
            InlineKeyboardButton(
                text=f"{labels[i]}. {opt[:40]}",
                callback_data=f"set_correct:{question_id}:{i}",
            )
        )
    return builder.as_markup()


def question_management_kb(quiz_id: str, question_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑️ Delete Question", callback_data=f"q_delete:{quiz_id}:{question_id}"),
        InlineKeyboardButton(text="◀️ Back", callback_data=f"quiz_view:{quiz_id}"),
    )
    return builder.as_markup()


def timer_selection_kb(quiz_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    timers = [10, 15, 20, 30, 45, 60, 90, 120]
    buttons = [
        InlineKeyboardButton(text=f"{t}s", callback_data=f"set_timer:{quiz_id}:{t}")
        for t in timers
    ]
    builder.add(*buttons)
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data=f"quiz_settings:{quiz_id}"))
    return builder.as_markup()


def score_selection_kb(quiz_id: str, score_type: str) -> InlineKeyboardMarkup:
    """score_type: 'correct' or 'wrong'"""
    builder = InlineKeyboardBuilder()
    if score_type == "correct":
        values = [1, 2, 3, 4, 5, 10]
    else:
        values = [0, -1, -2, -3, -4, -5]
    buttons = [
        InlineKeyboardButton(text=str(v), callback_data=f"set_score:{quiz_id}:{score_type}:{v}")
        for v in values
    ]
    builder.add(*buttons)
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data=f"quiz_settings:{quiz_id}"))
    return builder.as_markup()


def get_result_pdf_kb(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📄 Download PDF Result", callback_data=f"result_pdf:{session_id}"),
    )
    return builder.as_markup()
