from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import random


@dataclass
class QuizOption:
    text: str
    is_correct: bool = False

    def to_dict(self) -> Dict:
        return {"text": self.text, "is_correct": self.is_correct}

    @classmethod
    def from_dict(cls, data: Dict) -> "QuizOption":
        return cls(text=data["text"], is_correct=data.get("is_correct", False))


@dataclass
class QuizQuestion:
    question_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str = ""
    options: List[QuizOption] = field(default_factory=list)
    explanation: str = ""
    timer: int = 30
    poll_message_id: Optional[int] = None

    @property
    def correct_option_index(self) -> int:
        for i, opt in enumerate(self.options):
            if opt.is_correct:
                return i
        return 0

    def to_dict(self) -> Dict:
        return {
            "question_id": self.question_id,
            "text": self.text,
            "options": [o.to_dict() for o in self.options],
            "explanation": self.explanation,
            "timer": self.timer,
            "poll_message_id": self.poll_message_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "QuizQuestion":
        return cls(
            question_id=data.get("question_id", str(uuid.uuid4())[:8]),
            text=data["text"],
            options=[QuizOption.from_dict(o) for o in data.get("options", [])],
            explanation=data.get("explanation", ""),
            timer=data.get("timer", 30),
            poll_message_id=data.get("poll_message_id"),
        )

    def shuffled_options(self) -> List[QuizOption]:
        opts = self.options.copy()
        random.shuffle(opts)
        return opts


@dataclass
class Quiz:
    quiz_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str = ""
    creator_id: int = 0
    creator_name: str = ""
    questions: List[QuizQuestion] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    play_count: int = 0

    def __post_init__(self):
        defaults = {
            "shuffle_questions": True,
            "shuffle_options": True,
            "negative_marking": True,
            "correct_score": 4,
            "wrong_penalty": -1,
            "skip_score": 0,
            "exam_mode": False,
            "default_timer": 30,
        }
        for k, v in defaults.items():
            self.settings.setdefault(k, v)

    def to_dict(self) -> Dict:
        return {
            "quiz_id": self.quiz_id,
            "title": self.title,
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "questions": [q.to_dict() for q in self.questions],
            "settings": self.settings,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            "play_count": self.play_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Quiz":
        q = cls(
            quiz_id=data["quiz_id"],
            title=data["title"],
            creator_id=data["creator_id"],
            creator_name=data.get("creator_name", ""),
            questions=[QuizQuestion.from_dict(q) for q in data.get("questions", [])],
            settings=data.get("settings", {}),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            is_active=data.get("is_active", True),
            play_count=data.get("play_count", 0),
        )
        # Fill missing setting defaults
        defaults = {
            "shuffle_questions": True,
            "shuffle_options": True,
            "negative_marking": True,
            "correct_score": 4,
            "wrong_penalty": -1,
            "skip_score": 0,
            "exam_mode": False,
            "default_timer": 30,
        }
        for k, v in defaults.items():
            q.settings.setdefault(k, v)
        return q

    def get_questions_ordered(self) -> List[QuizQuestion]:
        qs = self.questions.copy()
        if self.settings.get("shuffle_questions"):
            random.shuffle(qs)
        return qs
