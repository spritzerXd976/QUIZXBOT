import pytest
import mongomock_motor
from unittest.mock import patch
from quiz_bot.database import db

@pytest.mark.asyncio
async def test_db_setup():
    with patch("quiz_bot.database.db.AsyncIOMotorClient", new=mongomock_motor.AsyncMongoMockClient):
        from quiz_bot.database.db import Database
        mock_db = Database()

        # Test basic insertion and retrieval
        await mock_db.users.insert_one({"user_id": 12345, "name": "Test User"})
        user = await mock_db.users.find_one({"user_id": 12345})

        assert user is not None
        assert user["name"] == "Test User"
