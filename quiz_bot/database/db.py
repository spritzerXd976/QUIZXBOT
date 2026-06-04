from motor.motor_asyncio import AsyncIOMotorClient
from quiz_bot.config import MONGODB_URI, DB_NAME

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DB_NAME]

        # Collections
        self.users = self.db.users
        self.quizzes = self.db.quizzes
        self.quiz_questions = self.db.quiz_questions
        self.sessions = self.db.sessions
        self.attempts = self.db.attempts
        self.leaderboard = self.db.leaderboard
        self.results = self.db.results

db = Database()

async def get_db():
    return db
