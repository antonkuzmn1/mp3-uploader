import math
import os.path
import traceback
from asyncio import sleep

from aiogram import Router, F
from aiogram.types import Message, FSInputFile

from src import logger, config
from src.telegram.exceptions import TelegramError

router = Router()


@router.message(F.audio)
async def handle_audio(message: Message):
    username = message.from_user.username
    logger.info(f'[handle_audio] {username}')
    audio = message.audio

    answer_status: Message | None = None
    try:
        if audio:
            file_size_mb = math.floor(audio.file_size / 1024 / 1024)
            allowed_size_mb = 48
            if file_size_mb > allowed_size_mb:
                msg = f'file too big: {file_size_mb}MB > {allowed_size_mb}MB'
                await message.answer(msg)
                logger.info(f'[handle_message] Reply to {username}: {msg}')
                raise TelegramError()

            file_id = audio.file_unique_id
            destination = f'{config.STORAGE_DIR}/{file_id}'

            file = await message.bot.get_file(audio.file_id)
            if not os.path.isfile(f'{destination}.mp3'):
                await message.bot.download_file(file.file_path, destination=f'{destination}.mp3')

            if audio.thumbnail:
                thumb = audio.thumb
                file = await message.bot.get_file(thumb.get('file_id'))
                if not os.path.isfile(f'{destination}.jpg'):
                    await message.bot.download_file(file.file_path, destination=f'{destination}.jpg')

                await message.answer_photo(
                    photo=FSInputFile(f'{destination}.jpg'),
                    caption=f'{config.MP3_STORAGE_URL}{file_id}.mp3',
                    show_caption_above_media=False,
                )

            else:
                await message.answer(f'{config.MP3_STORAGE_URL}{file_id}.mp3')

    except TypeError:
        traceback.print_exc()
        msg = 'something went wrong :('
        await message.answer(msg)
        logger.info(f'[handle_audio] Reply to {username}: {msg}')

    except TelegramError:
        pass

    finally:
        if answer_status is not None:
            await sleep(5)
            await answer_status.delete()