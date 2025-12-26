from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message

from src import logger, config


class AccessPermissionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        chat_id = event.chat.id
        logger.info(f'[AccessPermissionMiddleware] Attempt from username: {event.from_user.username}')

        if event.text == '/start':
            logger.info(f'[AccessPermissionMiddleware] {event.from_user.username}: {event.text}')
            return None

        # if chat_id not in config.PERMITTED_IDS:
        #     return None

        return await handler(event, data)