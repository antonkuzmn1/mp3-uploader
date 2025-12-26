import asyncio

from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src import logger, config
from src.telegram.handlers import audio_router, text_router
from src.telegram.middleware import AccessPermissionMiddleware

load_dotenv()

dp = Dispatcher()
dp.message.middleware(AccessPermissionMiddleware())
dp.include_routers(audio_router, text_router)


async def start():
    bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


@dp.startup()
def startup():
    logger.info('Started!')


if __name__ == "__main__":
    asyncio.run(start())