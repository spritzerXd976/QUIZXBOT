"""
Telegram MCQ Quiz Bot
Entry point — registers all routers, sets up DB, starts polling.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from aiohttp import web
from config import BOT_TOKEN
from database import connect_db, disconnect_db
from handlers import start_router, creation_router, play_router, profile_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def webapp_handler(request):
    return web.FileResponse('static/webapp.html')

async def start_web_app():
    app = web.Application()
    app.router.add_get('/webapp', webapp_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("🌐 Web App server running on port 8080")
    return runner


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in .env file!")
        sys.exit(1)

    # Connect to MongoDB
    await connect_db()

    # Initialize bot and dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers (order matters — more specific first)
    dp.include_router(start_router)
    dp.include_router(creation_router)
    dp.include_router(play_router)
    dp.include_router(profile_router)

    # Set bot commands
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="create", description="Create a new quiz"),
        BotCommand(command="quizzes", description="View your quizzes"),
        BotCommand(command="leaderboard", description="Global leaderboard"),
        BotCommand(command="profile", description="Your profile & stats"),
        BotCommand(command="stopquiz", description="Stop current quiz"),
        BotCommand(command="help", description="Help & commands"),
        BotCommand(command="cancel", description="Cancel current operation"),
    ])

    logger.info("🤖 Quiz Bot starting...")

    web_runner = await start_web_app()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await web_runner.cleanup()
        await disconnect_db()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
