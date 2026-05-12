from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ParticipantScore:
    user_id: int
    username: str
    first_name: str
    correct: int = 0
    wrong: int = 0
    missed: int = 0
    score: float = 0.0
    time_taken: float = 0.0
    answers: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "correct": self.correct,
            "wrong": self.wrong,
            "missed": self.missed,
            "score": self.score,
            "time_taken": self.time_taken,
            "answers": self.answers,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ParticipantScore":
        return cls(
            user_id=data["user_id"],
            username=data.get("username", ""),
            first_name=data.get("first_name", ""),
            correct=data.get("correct", 0),
            wrong=data.get("wrong", 0),
            missed=data.get("missed", 0),
            score=data.get("score", 0.0),
            time_taken=data.get("time_taken", 0.0),
            answers=data.get("answers", []),
        )

    @property
    def total_answered(self) -> int:
        return self.correct + self.wrong


@dataclass
class QuizSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    quiz_id: str = ""
    chat_id: int = 0
    chat_type: str = "private"
    started_by: int = 0
    started_by_name: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    current_question_index: int = 0
    question_order: List[str] = field(default_factory=list)  # question_ids in play order
    participants: Dict[int, ParticipantScore] = field(default_factory=dict)
    current_poll_message_id: Optional[int] = None
    current_poll_id: Optional[str] = None
    question_start_time: Optional[datetime] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    answered_this_round: List[int] = field(default_factory=list)  # user_ids who answered current q

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "quiz_id": self.quiz_id,
            "chat_id": self.chat_id,
            "chat_type": self.chat_type,
            "started_by": self.started_by,
            "started_by_name": self.started_by_name,
            "status": self.status.value,
            "current_question_index": self.current_question_index,
            "question_order": self.question_order,
            "participants": {str(k): v.to_dict() for k, v in self.participants.items()},
            "current_poll_message_id": self.current_poll_message_id,
            "current_poll_id": self.current_poll_id,
            "question_start_time": self.question_start_time,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "paused_at": self.paused_at,
            "answered_this_round": self.answered_this_round,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "QuizSession":
        participants = {
            int(k): ParticipantScore.from_dict(v)
            for k, v in data.get("participants", {}).items()
        }
        return cls(
            session_id=data["session_id"],
            quiz_id=data["quiz_id"],
            chat_id=data["chat_id"],
            chat_type=data.get("chat_type", "private"),
            started_by=data["started_by"],
            started_by_name=data.get("started_by_name", ""),
            status=SessionStatus(data.get("status", "active")),
            current_question_index=data.get("current_question_index", 0),
            question_order=data.get("question_order", []),
            participants=participants,
            current_poll_message_id=data.get("current_poll_message_id"),
            current_poll_id=data.get("current_poll_id"),
            question_start_time=data.get("question_start_time"),
            started_at=data.get("started_at", datetime.utcnow()),
            ended_at=data.get("ended_at"),
            paused_at=data.get("paused_at"),
            answered_this_round=data.get("answered_this_round", []),
        )

    def get_sorted_participants(self) -> List[ParticipantScore]:
        return sorted(
            self.participants.values(),
            key=lambda p: (-p.score, p.time_taken),
        )

    @property
    def total_questions(self) -> int:
        return len(self.question_order)

    @property
    def is_last_question(self) -> bool:
        return self.current_question_index >= self.total_questions - 1
