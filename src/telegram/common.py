import asyncio
import math
import os
import traceback
from asyncio import sleep

import yt_dlp
from aiogram.types import BufferedInputFile, FSInputFile, Message

from src import logger, config
from src import utils
from src.telegram.exceptions import TelegramError


async def send_track(
    message: Message,
    v_id: str,
    url: str,
    path: str,
    playlist: utils.PlaylistContext | None = None,
):
    meta = utils.read_meta(f'{path}.mp3')
    audio_path = f'{path}.mp3'
    if playlist is not None:
        audio_path = await utils.make_playlist_copy(path, playlist)
    thumbnail = await utils.make_thumbnail(f'{path}.mp3')
    try:
        await message.answer_audio(
            audio=FSInputFile(audio_path, filename=f'{meta.artist} - {meta.title}.mp3' if meta else None),
            thumbnail=BufferedInputFile(thumbnail, filename='cover.jpg') if thumbnail else None,
            title=meta.title if meta else None,
            performer=meta.artist if meta else None,
            duration=meta.duration if meta else None,
            caption=f'{url}\n{config.MP3_STORAGE_URL}{v_id}.mp3',
        )
    finally:
        if audio_path != f'{path}.mp3' and os.path.isfile(audio_path):
            os.remove(audio_path)


async def send_track_if_already_exists(
    message: Message, v_id: str, url: str, path: str, playlist: utils.PlaylistContext | None = None,
):
    username = message.from_user.username
    if os.path.isfile(f'{path}.mp3'):
        await utils.upgrade_legacy(path)
        await send_track(message, v_id, url, path, playlist)
        logger.info(f'[send_track_if_already_exists] Reply to {username}: {f'{v_id}.mp3'}')
        raise TelegramError()


async def download_single_track(message: Message, v_id: str, playlist: utils.PlaylistContext | None = None):
    username = message.from_user.username
    url = utils.get_url_by_v_id(v_id)

    answer_status: Message | None = None
    try:
        path = f'{config.STORAGE_DIR}/{v_id}'
        await send_track_if_already_exists(message, v_id, url, path, playlist)

        text_status = f'source: {url}\n\nawaiting...'
        answer_status = await message.answer(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: awaiting {f'{v_id}.mp3'}')
        await utils.verify_audio_duration(url)

        await send_track_if_already_exists(message, v_id, url, path, playlist)
        text_status += f'\n[1/3] downloadng...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: downloading {f'{v_id}.mp3'}')
        info = await utils.download_audio(url, path)

        meta = utils.meta_from_info(info)
        title = meta.title

        text_status += f'\n[2/3] converting...'
        await answer_status.edit_text(text_status, disable_web_page_preview=False)
        logger.info(f'[download_single_track] Reply to {username}: converting {f'{v_id}.mp3'}')
        await utils.process_downloaded(path, meta)

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
        else:
            await send_track(message, v_id, url, path, playlist)
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

    info = await utils.get_info(url, flat=True)
    entries = info.get('entries')

    if entries is None:
        msg = 'something went wrong :(\n{url}'
        await message.answer(msg)
        logger.info(f'[download_playlist] Reply to {username}: {msg}')
        return

    semaphore = asyncio.Semaphore(max_concurrent_downloads)

    entries = list(entries)
    playlist_title = info.get('title') or list_id
    playlist_artist = utils._clean_artist(info.get('uploader') or info.get('channel'))

    async def worker(index: int, entry: dict):
        v_id = entry.get('id')
        if not v_id:
            return

        playlist = utils.PlaylistContext(
            title=playlist_title, index=index, total=len(entries), artist=playlist_artist,
        )
        async with semaphore:
            await download_single_track(message, v_id, playlist)
            await asyncio.sleep(1)

    tasks = [worker(i, entry) for i, entry in enumerate(entries, start=1)]
    await asyncio.gather(*tasks)

    text_status += f'\nsuccessfully success!'
    await answer_status.edit_text(text_status, disable_web_page_preview=False)
    logger.info(f'[download_playlist] Reply to {username}: success {f'{list_id}.mp3'}')
    await sleep(5)
    await answer_status.delete()