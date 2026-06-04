import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from quiz_bot.config import BOT_TOKEN, WEB_HOST, WEB_PORT
from quiz_bot.handlers import base, creation, manage, play
from quiz_bot.web.app import setup_app
from quiz_bot.services.scheduler import scheduler

logging.basicConfig(level=logging.INFO)

async def main():
    if BOT_TOKEN == "dummy_token_for_now":
        logging.warning("Using dummy bot token! Bot API calls will fail.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(base.router)
    dp.include_router(creation.router)
    dp.include_router(manage.router)
    dp.include_router(play.router)

    # Start scheduler
    scheduler.start()

    # Setup web app
    app = setup_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()

    logging.info(f"Web server started on http://{WEB_HOST}:{WEB_PORT}")

    # Start bot polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
