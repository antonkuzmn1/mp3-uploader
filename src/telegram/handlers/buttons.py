import asyncio
from asyncio import sleep

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.telegram import common

router = Router()


@router.callback_query(F.data.startswith('single:'))
async def handle_single(callback: CallbackQuery):
    v_id = callback.data.split(':')[1]
    await response_callback(callback)
    await common.download_single_track(callback.message, v_id)


@router.callback_query(F.data.startswith('playlist:'))
async def handle_playlist(callback: CallbackQuery):
    list_id = callback.data.split(':')[1]
    await response_callback(callback)
    await common.download_playlist(callback.message, list_id)


async def response_callback(callback: CallbackQuery):
    await callback.answer(cache_time=1)

    status_msg = await callback.message.edit_text('processing...')

    async def delete_later(msg):
        await sleep(3)
        await msg.delete()

    asyncio.create_task(delete_later(status_msg))