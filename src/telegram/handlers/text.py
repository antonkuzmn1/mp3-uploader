from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from src import logger
from src import utils
from src.telegram import common
from src.telegram.exceptions import TelegramError

router = Router()


@router.message(F.text)
async def handle_message(message: Message):
    username = message.from_user.username
    logger.info(f'[handle_message] {username}: {message.text}')
    url = message.text

    v_id = utils.get_v_id(url)
    list_id = utils.get_list_id(url)

    if v_id is None and list_id is None:
        msg_base = f'incorrect yt url link: <code>{url}</code>'
        msg = f'{msg_base}\n\nexample: https://www.youtube.com/watch?v=VIDEO_ID'
        await message.answer(msg)
        logger.info(f'[handle_message] Reply to {username}: {msg_base}')
        raise TelegramError()

    if v_id is not None and list_id is not None:
        await message.answer(
            'select an option to download',
            reply_markup=get_choice_keyboard(v_id, list_id),
        )
        return

    if v_id is not None and list_id is None:
        await common.download_single_track(message, v_id)

    if v_id is None and list_id is not None:
        await common.download_playlist(message, list_id)


def get_choice_keyboard(v_id: str, list_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='single track', callback_data=f'single:{v_id}'),
        InlineKeyboardButton(text='playlist', callback_data=f'playlist:{list_id}')
    ]])