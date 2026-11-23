import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from asyncio import get_running_loop
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs

import yt_dlp
from mutagen.id3 import (
    APIC, COMM, ID3, ID3NoHeaderError, TALB, TDRC, TIT2, TPE1, TPE2, TRCK, WOAS,
)
from mutagen.mp3 import MP3

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


async def get_info(url: str, flat: bool = False) -> dict:
    ydl_opts_intelligence = {'quiet': True, 'no_warnings': True}
    if flat:
        # Only list playlist entries instead of resolving every video.
        ydl_opts_intelligence['extract_flat'] = 'in_playlist'
    def blocking_get_info():
        with yt_dlp.YoutubeDL(ydl_opts_intelligence) as ydl:
            return ydl.extract_info(url, download=False)
    return await run_blocking(blocking_get_info)


async def verify_audio_duration(url: str, duration_limit: int = 3600):
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


@dataclass
class TrackMeta:
    title: str
    artist: str
    album: str | None = None
    year: str | None = None
    url: str | None = None
    duration: int = 0


@dataclass
class PlaylistContext:
    title: str
    index: int
    total: int
    artist: str | None = None


def _clean_artist(name: str | None) -> str | None:
    if name and name.endswith(' - Topic'):
        return name.removesuffix(' - Topic')
    return name


def meta_from_info(info: dict) -> TrackMeta:
    """Prefer YouTube Music fields (track/artist/album) over generic video fields."""
    title = info.get('track') or info.get('title') or info.get('id') or 'Unknown'
    artist = (
        info.get('artist')
        or info.get('creator')
        or _clean_artist(info.get('uploader'))
        or 'Unknown'
    )
    # yt-dlp may return several comma-separated artists; keep them as-is.
    year = info.get('release_year') or (info.get('upload_date') or '')[:4] or None
    return TrackMeta(
        title=title,
        artist=artist,
        album=info.get('album'),
        year=str(year) if year else None,
        url=info.get('webpage_url'),
        duration=int(info.get('duration') or 0),
    )


def read_meta(mp3_path: str) -> TrackMeta | None:
    try:
        audio = MP3(mp3_path)
    except Exception:
        return None
    tags = audio.tags or {}

    def text(frame: str) -> str | None:
        value = tags.get(frame)
        return str(value.text[0]) if value and value.text else None

    return TrackMeta(
        title=text('TIT2') or os.path.basename(mp3_path),
        artist=text('TPE1') or 'Unknown',
        album=text('TALB'),
        year=text('TDRC') or text('TYER'),
        duration=int(audio.info.length),
    )


def write_tags(
    mp3_path: str,
    meta: TrackMeta,
    cover_path: str | None = None,
    playlist: PlaylistContext | None = None,
):
    """Write ID3v2.3 tags (best player compatibility) and an embedded front cover."""
    try:
        tags = ID3(mp3_path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.setall('TIT2', [TIT2(encoding=3, text=meta.title)])
    tags.setall('TPE1', [TPE1(encoding=3, text=meta.artist)])
    album = playlist.title if playlist else meta.album
    if album:
        tags.setall('TALB', [TALB(encoding=3, text=album)])
    if playlist:
        tags.setall('TRCK', [TRCK(encoding=3, text=f'{playlist.index}/{playlist.total}')])
        if playlist.artist:
            tags.setall('TPE2', [TPE2(encoding=3, text=playlist.artist)])
    if meta.year:
        tags.setall('TDRC', [TDRC(encoding=3, text=meta.year)])
    if meta.url:
        tags.setall('WOAS', [WOAS(url=meta.url)])
        tags.setall('COMM', [COMM(encoding=3, lang='eng', desc='', text=meta.url)])
    if cover_path and os.path.isfile(cover_path):
        with open(cover_path, 'rb') as f:
            tags.setall('APIC', [APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=f.read())])

    tags.save(mp3_path, v2_version=3)


def _square_jpeg(src: str, dst: str, size: int):
    subprocess.run(
        [
            'ffmpeg', '-y', '-i', src,
            '-vf', f"crop='min(iw,ih)':'min(iw,ih)',scale={size}:{size}",
            '-q:v', '3',
            dst,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _find_thumbnail(path: str) -> str | None:
    for ext in ('webp', 'jpg', 'png', 'jpeg'):
        if os.path.isfile(f'{path}.{ext}'):
            return f'{path}.{ext}'
    return None


async def process_downloaded(path: str, meta: TrackMeta):
    """Make a 320px square thumbnail for Telegram/API and embed a 600px cover plus tags into the MP3."""
    def blocking():
        src = _find_thumbnail(path)
        cover = f'{path}.cover.jpg'
        thumb = f'{path}.jpg'
        if src:
            _square_jpeg(src, cover, 600)
            # Telegram requires thumbnails of at most 320x320.
            _square_jpeg(src, f'{path}.thumb.jpg', 320)
            if src != thumb:
                os.remove(src)
            os.replace(f'{path}.thumb.jpg', thumb)
        write_tags(f'{path}.mp3', meta, cover if os.path.isfile(cover) else None)
        if os.path.isfile(cover):
            os.remove(cover)

    await run_blocking(blocking)


async def make_playlist_copy(path: str, playlist: PlaylistContext) -> str:
    """Copy the cached MP3 to a temp file with album/track-number tags for this playlist.

    The stored file is shared by every request for this video, so playlist-specific
    tags never go into it.
    """
    def blocking():
        fd, tmp = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)
        shutil.copyfile(f'{path}.mp3', tmp)
        meta = read_meta(tmp)
        if meta:
            write_tags(tmp, meta, playlist=playlist)
        return tmp

    return await run_blocking(blocking)
