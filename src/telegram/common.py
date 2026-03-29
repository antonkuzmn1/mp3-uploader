import asyncio
import math
import os
import traceback
from asyncio import sleep

import yt_dlp
from aiogram.types import Message, FSInputFile

from src import logger, config
from src import utils
from src.telegram.exceptions import TelegramError


async def send_track_if_already_exists(message: Message, v_id: str, url: str, path: str):
    username = message.from_user.username
    if os.path.isfile(f'{path}.mp3') and os.path.isfile(f'{path}.jpg'):
        await message.answer_audio(
                audio=FSInputFile(f'{path}.mp3'),
                thumb=FSInputFile(f'{path}.jpg'),
                caption=f'{url}\n{config.MP3_STORAGE_URL}{v_id}.mp3',
        )
        logger.info(f'[send_track_if_already_exists] Reply to {username}: {f'{v_id}.mp3'}')
        raise TelegramError()


async def download_single_track(message: Message, v_id: str):
    username = message.from_user.username
    url = utils.get_url_by_v_id(v_id)

    answer_status: Message | None = None
    try:
        path = f'{config.STORAGE_DIR}/{v_id}'
        await send_track_if_already_exists(message, v_id, url, path)

        text_status = f'source: {url}\n\nawaiting...'
        answer_status = await message.answer(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: awaiting {f'{v_id}.mp3'}')
        await utils.verify_audio_duration(url)

        await send_track_if_already_exists(message, v_id, url, path)
        text_status += f'\n[1/3] downloadng...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: downloading {f'{v_id}.mp3'}')
        info = await utils.download_audio(url, path)

        title = info.get('title')
        uploader = info.get('uploader')

        text_status += f'\n[2/3] converting...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: converting {f'{v_id}.mp3'}')
        await utils.convert_thumbnail(path, title, uploader)

        text_status += f'\n[3/3] sending...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: sending {f'{v_id}.mp3'}')

        file_size_mb = os.path.getsize(f'{path}.mp3') / 1024 / 1024
        if file_size_mb > 48:
            msg = f'file "{title}" too big ({math.floor(file_size_mb)}MB > 48MB)\n\n{url}'
            await message.answer(msg, disable_web_page_preview=False)
            logger.info(f'[download_single_track] Reply to {username}: {msg}')

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
                caption=f'{url}\n{config.MP3_STORAGE_URL}{v_id}.mp3',
                performer=uploader,
            )
            logger.info(f'[download_single_track] Reply to {username}: {f'{v_id}.mp3'}')


    except yt_dlp.utils.DownloadError as e:
        if 'confirm your age' in str(e):
            await message.answer(
                f'downloading this video is not permitted cuz it is age-restricted on yt\n\n{url}',
                disable_web_page_preview=False,
            )
        else:
            traceback.print_exc()
            msg = 'something went wrong :('
            msg += f'\n{url}'
            await message.answer(msg)
            logger.info(f'[download_single_track] Reply to {username}: {msg}')

    except TypeError:
        traceback.print_exc()
        msg = 'something went wrong :('
        msg += f'\n{url}'
        await message.answer(msg)
        logger.info(f'[download_single_track] Reply to {username}: {msg}')

    except ValueError as e:
        if str(e) == 'Video is longer than 1 hour':
            msg = 'video is longer than 1 hour'
        elif str(e) == 'The video`s length could not be determined, but it may be a live broadcast':
            msg = 'it may be a live broadcast'
        else:
            traceback.print_exc()
            msg = 'something went wrong :('
        msg += f'\n{url}'
        await message.answer(msg)
        logger.info(f'[download_single_track] Reply to {username}: {msg}')

    except TelegramError:
        pass

    finally:
        if answer_status is not None:
            await sleep(5)
            await answer_status.delete()


async def download_playlist(message: Message, list_id: str, max_concurrent_downloads: int = 3):
    username = message.from_user.username
    url = utils.get_url_by_list_id(list_id)

    text_status = f'playlist: {url}\n\nprocessing...'
    answer_status = await message.answer(text_status, disable_web_page_preview=False)
    logger.info(f'[download_playlist] Reply to {username}: awaiting {f'{list_id}.mp3'}')

    info = await utils.get_info(url)
    entries = info.get('entries')

    if entries is None:
        msg = 'something went wrong :(\n{url}'
        await message.answer(msg)
        logger.info(f'[download_playlist] Reply to {username}: {msg}')
        return

    semaphore = asyncio.Semaphore(max_concurrent_downloads)

    async def worker(entry: dict):
        v_id = entry.get('id')
        if not v_id:
            return

        async with semaphore:
            await download_single_track(message, v_id)
            await asyncio.sleep(1)

    tasks = [worker(entry) for entry in entries]
    await asyncio.gather(*tasks)

    text_status += f'\nsuccessfully success!'
    await answer_status.edit_text(text_status, disable_web_page_preview=False)
    logger.info(f'[download_playlist] Reply to {username}: success {f'{list_id}.mp3'}')
    await sleep(5)
    await answer_status.delete()