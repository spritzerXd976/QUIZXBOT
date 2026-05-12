import os
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "8401941077:AAEbnjXGboH1g92HUWNQUOp4lyZOPzSro7E")

# Telegram API credentials
API_ID = int(os.getenv("API_ID", "12380656"))
API_HASH = os.getenv("API_HASH", "d927c13beaaf5110f25c505b7c071273")

# Database
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Mafia:Mafia@mafia.wvuzxgl.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "quiz_bot")

# Bot info
BOT_USERNAME = os.getenv("BOT_USERNAME", "YumiiXbot")

# Quiz settings
DEFAULT_QUESTION_TIMER = 30  # seconds
MIN_QUESTION_TIMER = 5
MAX_QUESTION_TIMER = 300
MIN_OPTIONS = 2
MAX_OPTIONS = 4

# Scoring
DEFAULT_CORRECT_SCORE = 4
DEFAULT_WRONG_PENALTY = -1
DEFAULT_SKIP_SCORE = 0

# Poll settings
POLL_TYPE_QUIZ = "quiz"

# States
class States:
    CREATING_QUIZ_TITLE = "creating_quiz_title"
    CREATING_QUESTION = "creating_question"
    CREATING_OPTIONS = "creating_options"
    SETTING_TIMER = "setting_timer"
    EDITING_QUIZ = "editing_quiz"
    WAITING_POLL = "waiting_poll"

# Collections
class Collections:
    USERS = "users"
    QUIZZES = "quizzes"
    SESSIONS = "sessions"
    ATTEMPTS = "attempts"
    LEADERBOARD = "leaderboard"