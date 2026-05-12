from typing import Optional, List
from datetime import datetime
from database import get_db
from models import QuizSession, ParticipantScore, SessionStatus
from config import Collections


async def create_session(session: QuizSession) -> QuizSession:
    db = get_db()
    await db[Collections.SESSIONS].insert_one(session.to_dict())
    return session


async def get_session(session_id: str) -> Optional[QuizSession]:
    db = get_db()
    doc = await db[Collections.SESSIONS].find_one({"session_id": session_id})
    return QuizSession.from_dict(doc) if doc else None


async def get_active_session_by_chat(chat_id: int) -> Optional[QuizSession]:
    db = get_db()
    doc = await db[Collections.SESSIONS].find_one({
        "chat_id": chat_id,
        "status": {"$in": [SessionStatus.ACTIVE.value, SessionStatus.PAUSED.value]},
    })
    return QuizSession.from_dict(doc) if doc else None


async def get_active_session_by_quiz(quiz_id: str, chat_id: int) -> Optional[QuizSession]:
    db = get_db()
    doc = await db[Collections.SESSIONS].find_one({
        "quiz_id": quiz_id,
        "chat_id": chat_id,
        "status": {"$in": [SessionStatus.ACTIVE.value, SessionStatus.PAUSED.value]},
    })
    return QuizSession.from_dict(doc) if doc else None


async def update_session(session: QuizSession) -> bool:
    db = get_db()
    result = await db[Collections.SESSIONS].replace_one(
        {"session_id": session.session_id}, session.to_dict()
    )
    return result.modified_count > 0


async def pause_session(session_id: str) -> bool:
    db = get_db()
    result = await db[Collections.SESSIONS].update_one(
        {"session_id": session_id},
        {"$set": {"status": SessionStatus.PAUSED.value, "paused_at": datetime.utcnow()}},
    )
    return result.modified_count > 0


async def resume_session(session_id: str) -> bool:
    db = get_db()
    result = await db[Collections.SESSIONS].update_one(
        {"session_id": session_id},
        {"$set": {"status": SessionStatus.ACTIVE.value, "paused_at": None}},
    )
    return result.modified_count > 0


async def end_session(session_id: str) -> bool:
    db = get_db()
    result = await db[Collections.SESSIONS].update_one(
        {"session_id": session_id},
        {"$set": {"status": SessionStatus.COMPLETED.value, "ended_at": datetime.utcnow()}},
    )
    return result.modified_count > 0


async def cancel_session(session_id: str) -> bool:
    db = get_db()
    result = await db[Collections.SESSIONS].update_one(
        {"session_id": session_id},
        {"$set": {"status": SessionStatus.CANCELLED.value, "ended_at": datetime.utcnow()}},
    )
    return result.modified_count > 0


async def ensure_participant(session: QuizSession, user_id: int, username: str, first_name: str):
    if user_id not in session.participants:
        session.participants[user_id] = ParticipantScore(
            user_id=user_id,
            username=username,
            first_name=first_name,
        )


async def record_answer(
    session: QuizSession,
    user_id: int,
    username: str,
    first_name: str,
    question_id: str,
    selected_option: int,
    correct_option: int,
    time_taken: float,
    correct_score: float,
    wrong_penalty: float,
    negative_marking: bool,
) -> str:
    """Returns: 'correct', 'wrong', 'already_answered'"""
    await ensure_participant(session, user_id, username, first_name)
    participant = session.participants[user_id]

    # Check if already answered this question
    answered_qs = [a["question_id"] for a in participant.answers]
    if question_id in answered_qs:
        return "already_answered"

    is_correct = selected_option == correct_option
    if is_correct:
        participant.correct += 1
        participant.score += correct_score
        result = "correct"
    else:
        participant.wrong += 1
        if negative_marking:
            participant.score += wrong_penalty
        result = "wrong"

    participant.time_taken += time_taken
    participant.answers.append({
        "question_id": question_id,
        "selected": selected_option,
        "correct": correct_option,
        "is_correct": is_correct,
        "time_taken": time_taken,
    })

    if user_id not in session.answered_this_round:
        session.answered_this_round.append(user_id)

    return result


async def mark_missed_question(session: QuizSession, question_id: str):
    """Mark all participants who didn't answer as missed."""
    for uid, participant in session.participants.items():
        answered_qs = [a["question_id"] for a in participant.answers]
        if question_id not in answered_qs:
            participant.missed += 1
            participant.answers.append({
                "question_id": question_id,
                "selected": -1,
                "correct": -1,
                "is_correct": False,
                "time_taken": 0,
                "missed": True,
            })


async def update_leaderboard(session: QuizSession, quiz_id: str):
    db = get_db()
    for user_id, participant in session.participants.items():
        total_q = session.total_questions
        percentage = (participant.correct / total_q * 100) if total_q > 0 else 0
        await db[Collections.LEADERBOARD].update_one(
            {"quiz_id": quiz_id, "user_id": user_id},
            {
                "$set": {
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_score": participant.score,
                    "last_percentage": percentage,
                    "last_correct": participant.correct,
                    "last_wrong": participant.wrong,
                    "last_missed": participant.missed,
                    "last_time": participant.time_taken,
                    "last_played": datetime.utcnow(),
                },
                "$max": {"best_score": participant.score, "best_percentage": percentage},
                "$inc": {"total_attempts": 1},
                "$setOnInsert": {"first_played": datetime.utcnow()},
            },
            upsert=True,
        )


async def get_quiz_leaderboard(quiz_id: str, limit: int = 10) -> List[dict]:
    db = get_db()
    cursor = db[Collections.LEADERBOARD].find(
        {"quiz_id": quiz_id},
        sort=[("best_score", -1), ("last_time", 1)],
        limit=limit,
    )
    return await cursor.to_list(length=limit)
