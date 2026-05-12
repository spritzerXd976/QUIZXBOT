from typing import Optional
from datetime import datetime
from database import get_db
from models import User
from config import Collections


async def get_or_create_user(user_id: int, username: str = "", first_name: str = "", last_name: str = "") -> User:
    db = get_db()
    doc = await db[Collections.USERS].find_one({"user_id": user_id})
    if doc:
        user = User.from_dict(doc)
        # Update name info
        await db[Collections.USERS].update_one(
            {"user_id": user_id},
            {"$set": {"username": username, "first_name": first_name, "last_name": last_name}},
        )
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        return user

    user = User(
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    await db[Collections.USERS].insert_one(user.to_dict())
    return user


async def get_user(user_id: int) -> Optional[User]:
    db = get_db()
    doc = await db[Collections.USERS].find_one({"user_id": user_id})
    return User.from_dict(doc) if doc else None


async def update_user_stats(user_id: int, correct: int, wrong: int, missed: int, score: float, percentage: float):
    db = get_db()
    await db[Collections.USERS].update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "total_quizzes_taken": 1,
                "total_correct": correct,
                "total_wrong": wrong,
                "total_missed": missed,
                "total_score": score,
            },
            "$max": {"best_percentage": percentage},
        },
    )


async def increment_quiz_created(user_id: int):
    db = get_db()
    await db[Collections.USERS].update_one(
        {"user_id": user_id},
        {"$inc": {"total_quizzes_created": 1}},
    )
