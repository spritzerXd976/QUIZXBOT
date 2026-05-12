from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime


@dataclass
class User:
    user_id: int
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    joined_at: datetime = field(default_factory=datetime.utcnow)
    total_quizzes_taken: int = 0
    total_quizzes_created: int = 0
    total_correct: int = 0
    total_wrong: int = 0
    total_missed: int = 0
    total_score: float = 0.0
    best_percentage: float = 0.0

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.full_name

    @property
    def total_answered(self) -> int:
        return self.total_correct + self.total_wrong

    @property
    def accuracy(self) -> float:
        if self.total_answered == 0:
            return 0.0
        return (self.total_correct / self.total_answered) * 100

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "joined_at": self.joined_at,
            "total_quizzes_taken": self.total_quizzes_taken,
            "total_quizzes_created": self.total_quizzes_created,
            "total_correct": self.total_correct,
            "total_wrong": self.total_wrong,
            "total_missed": self.total_missed,
            "total_score": self.total_score,
            "best_percentage": self.best_percentage,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data.get("username", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            joined_at=data.get("joined_at", datetime.utcnow()),
            total_quizzes_taken=data.get("total_quizzes_taken", 0),
            total_quizzes_created=data.get("total_quizzes_created", 0),
            total_correct=data.get("total_correct", 0),
            total_wrong=data.get("total_wrong", 0),
            total_missed=data.get("total_missed", 0),
            total_score=data.get("total_score", 0.0),
            best_percentage=data.get("best_percentage", 0.0),
        )
