from typing import List, Optional, Dict
from datetime import datetime
import copy
import uuid
from database import get_db
from models import Quiz, QuizQuestion
from config import Collections


async def create_quiz(quiz: Quiz) -> Quiz:
    db = get_db()
    await db[Collections.QUIZZES].insert_one(quiz.to_dict())
    return quiz


async def get_quiz(quiz_id: str) -> Optional[Quiz]:
    db = get_db()
    doc = await db[Collections.QUIZZES].find_one({"quiz_id": quiz_id})
    return Quiz.from_dict(doc) if doc else None


async def get_user_quizzes(creator_id: int) -> List[Quiz]:
    db = get_db()
    cursor = db[Collections.QUIZZES].find(
        {"creator_id": creator_id, "is_active": True},
        sort=[("created_at", -1)]
    )
    docs = await cursor.to_list(length=100)
    return [Quiz.from_dict(d) for d in docs]


async def update_quiz(quiz: Quiz) -> bool:
    db = get_db()
    quiz.updated_at = datetime.utcnow()
    result = await db[Collections.QUIZZES].replace_one(
        {"quiz_id": quiz.quiz_id}, quiz.to_dict()
    )
    return result.modified_count > 0


async def delete_quiz(quiz_id: str) -> bool:
    db = get_db()
    result = await db[Collections.QUIZZES].update_one(
        {"quiz_id": quiz_id}, {"$set": {"is_active": False}}
    )
    return result.modified_count > 0


async def duplicate_quiz(quiz_id: str, creator_id: int, creator_name: str) -> Optional[Quiz]:
    original = await get_quiz(quiz_id)
    if not original:
        return None
    new_quiz = copy.deepcopy(original)
    new_quiz.quiz_id = str(uuid.uuid4())[:12]
    new_quiz.title = f"Copy of {original.title}"
    new_quiz.creator_id = creator_id
    new_quiz.creator_name = creator_name
    new_quiz.created_at = datetime.utcnow()
    new_quiz.updated_at = datetime.utcnow()
    new_quiz.play_count = 0
    # Regenerate question IDs
    for q in new_quiz.questions:
        q.question_id = str(uuid.uuid4())[:8]
    await create_quiz(new_quiz)
    return new_quiz


async def add_question_to_quiz(quiz_id: str, question: QuizQuestion) -> bool:
    db = get_db()
    result = await db[Collections.QUIZZES].update_one(
        {"quiz_id": quiz_id},
        {
            "$push": {"questions": question.to_dict()},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )
    return result.modified_count > 0


async def delete_question_from_quiz(quiz_id: str, question_id: str) -> bool:
    db = get_db()
    result = await db[Collections.QUIZZES].update_one(
        {"quiz_id": quiz_id},
        {
            "$pull": {"questions": {"question_id": question_id}},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )
    return result.modified_count > 0


async def increment_play_count(quiz_id: str):
    db = get_db()
    await db[Collections.QUIZZES].update_one(
        {"quiz_id": quiz_id}, {"$inc": {"play_count": 1}}
    )


async def update_quiz_settings(quiz_id: str, settings: Dict) -> bool:
    db = get_db()
    update_data = {f"settings.{k}": v for k, v in settings.items()}
    update_data["updated_at"] = datetime.utcnow()
    result = await db[Collections.QUIZZES].update_one(
        {"quiz_id": quiz_id}, {"$set": update_data}
    )
    return result.modified_count > 0
