from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME, Collections

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    await create_indexes()
    print(f"✅ Connected to MongoDB: {DB_NAME}")


async def disconnect_db():
    global client
    if client:
        client.close()
        print("❌ Disconnected from MongoDB")


async def create_indexes():
    await db[Collections.USERS].create_index("user_id", unique=True)
    await db[Collections.QUIZZES].create_index("quiz_id", unique=True)
    await db[Collections.QUIZZES].create_index("creator_id")
    await db[Collections.SESSIONS].create_index("session_id", unique=True)
    await db[Collections.SESSIONS].create_index("quiz_id")
    await db[Collections.SESSIONS].create_index("chat_id")
    await db[Collections.ATTEMPTS].create_index([("session_id", 1), ("user_id", 1)])
    await db[Collections.LEADERBOARD].create_index([("quiz_id", 1), ("user_id", 1)], unique=True)


def get_db():
    return db
