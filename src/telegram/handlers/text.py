import math
import os
import traceback
from asyncio import sleep

import yt_dlp
from aiogram import Router, F
from aiogram.types import Message, FSInputFile

from src import logger, config
from src.telegram.exceptions import TelegramError
from src import utils
from src.utils import download_audio, convert_thumbnail

router = Router()


@router.message(F.text)
async def handle_message(message: Message):
    username = message.from_user.username
    logger.info(f'[handle_message] {username}: {message.text}')
    url = message.text
    video_id = utils.get_id_from_url(url)

    answer_status: Message | None = None
    try:
        if video_id is None:
            msg_base = f'incorrect yt url link: <code>{url}</code>'
            msg = f'{msg_base}\n\nexample: https://www.youtube.com/watch?v=VIDEO_ID'
            await message.answer(msg)
            logger.info(f'[handle_message] Reply to {username}: {msg_base}')
            raise TelegramError()

        path = f'{config.STORAGE_DIR}/{video_id}'
        if os.path.isfile(f'{path}.mp3') and os.path.isfile(f'{path}.jpg'):
            await message.answer_audio(
                    audio=FSInputFile(f'{path}.mp3'),
                    thumb=FSInputFile(f'{path}.jpg'),
                    caption=f'{url}\n{config.MP3_STORAGE_URL}{video_id}.mp3',
            )
            logger.info(f'[handle_message] Reply to {username}: {f'{video_id}.mp3'}')
            raise TelegramError()

        text_status = f'answer to @{username}\n\nsource: {url}\n\n[1/3] downloadng...'
        answer_status = await message.answer(text_status, disable_web_page_preview=False)
        logger.info(f'[handle_message] Reply to {username}: downloading {f'{video_id}.mp3'}')

        info = await download_audio(url, path)

        title = info.get('title')
        uploader = info.get('uploader')

        text_status += f'\n[2/3] converting...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[handle_message] Reply to {username}: converting {f'{video_id}.mp3'}')

        await convert_thumbnail(path, title, uploader)

        text_status += f'\n[3/3] sending...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[handle_message] Reply to {username}: sending {f'{video_id}.mp3'}')

        file_size_mb = os.path.getsize(f'{path}.mp3') / 1024 / 1024
        if file_size_mb > 48:
            msg = f'file "{title}" too big ({math.floor(file_size_mb)}MB > 48MB)\n\n{url}'
            await message.answer(msg, disable_web_page_preview=False)
            logger.info(f'[handle_message] Reply to {username}: {msg}')

            if os.path.isfile(f'{path}.mp3'):
                os.remove(f'{path}.mp3')
            if os.path.isfile(f'{path}.jpg'):
                os.remove(f'{path}.jpg')
        else:
            await message.answer_audio(
                audio=FSInputFile(f'{path}.mp3'),
                thumb=FSInputFile(f'{path}.jpg'),
                title=title,
                duration=int(info.get('duration', 0)),
                caption=f'{url}\n{config.MP3_STORAGE_URL}{video_id}.mp3',
                performer=uploader,
            )
            logger.info(f'[handle_message] Reply to {username}: {f'{video_id}.mp3'}')


    except yt_dlp.utils.DownloadError as e:
        if 'confirm your age' in str(e):
            await message.answer(
                f'downloading this video is not permitted cuz it is age-restricted on yt\n\n{url}',
                disable_web_page_preview=False,
            )
        else:
            traceback.print_exc()
            msg = 'something went wrong :('
            await message.answer(msg)
            logger.info(f'[handle_message] Reply to {username}: {msg}')

    except TypeError:
        traceback.print_exc()
        msg = 'something went wrong :('
        await message.answer(msg)
        logger.info(f'[handle_message] Reply to {username}: {msg}')

    except ValueError as e:
        if str(e) == 'Video is longer than 1 hour':
            msg = 'video is longer than 1 hour'
            await message.answer(msg)
            logger.info(f'[handle_audio] Reply to {username}: {msg}')
        elif str(e) == 'The video`s length could not be determined, but it may be a live broadcast':
            msg = 'it may be a live broadcast'
            await message.answer(msg)
            logger.info(f'[handle_audio] Reply to {username}: {msg}')
        else:
            traceback.print_exc()
            msg = 'something went wrong :('
            await message.answer(msg)
            logger.info(f'[handle_message] Reply to {username}: {msg}')

    except TelegramError:
        pass

    finally:
        if answer_status is not None:
            await sleep(5)
            await answer_status.delete()
