import os
import subprocess
from asyncio import get_running_loop
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs

import yt_dlp

from src import logger

executor = ThreadPoolExecutor(max_workers=2)


def get_v_id(url: str) -> str | None:
    parsed = urlparse(url)

    qs = parse_qs(parsed.query)
    if 'v' in qs:
        return qs['v'][0]

    if parsed.netloc in ('youtu.be', 'www.youtu.be'):
        return parsed.path.lstrip('/')

    return None


def get_list_id(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    list_id = qs.get('list', [None])[0]

    if list_id is not None and not list_id.startswith('RD'):
        return list_id

    return None


def get_url_by_v_id(video_id: str) -> str:
    return f'https://www.youtube.com/watch?v={video_id}'


def get_url_by_list_id(list_id: str) -> str:
    return f'https://www.youtube.com/playlist?list={list_id}'


async def run_blocking(func):
    loop = get_running_loop()
    # noinspection PyTypeChecker
    return await loop.run_in_executor(executor, func)


async def get_info(url: str) -> dict:
    ydl_opts_intelligence = {'quiet': True, 'no_warnings': True}
    def blocking_get_info():
        with yt_dlp.YoutubeDL(ydl_opts_intelligence) as ydl:
            return ydl.extract_info(url, download=False)
    return await run_blocking(blocking_get_info)


async def verify_audio_duration(url: str, duration_limit: int = 3600 * 6):
    logger.info(f'[download_audio] Reconnaissance is underway...')
    info = await get_info(url)
    duration = info.get('duration')
    logger.info(f'[download_audio] Reconnaissance result: {duration} seconds')

    if duration is None:
        raise ValueError('The video`s length could not be determined, but it may be a live broadcast')

    if duration is not None and duration > duration_limit:
        raise ValueError('Video is longer than 1 hour')


async def download_audio(url: str, path: str, bitrate: int = 128):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'logger': None,
        'no_warnings': True,
        'outtmpl': f'{path}.%(ext)s',
        'writethumbnail': True,
        'postprocessors': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': str(bitrate)},
            {'key': 'FFmpegMetadata'},
        ],
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 14)',
        },
    }

    def blocking_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    return await run_blocking(blocking_download)


async def convert_thumbnail(path: str, title: str, uploader: str):
    def blocking_convert():
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", f'{path}.webp',
                "-metadata", f'title={title}',
                "-metadata", f'artist={uploader}',
                "-metadata", f'album=YouTube',
                "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=320:320",
                f'{path}.jpg',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if os.path.isfile(f'{path}.webp'):
            os.remove(f'{path}.webp')

    await run_blocking(blocking_convert)
