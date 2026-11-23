import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from asyncio import get_running_loop
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

import yt_dlp
from mutagen.id3 import (
    APIC, COMM, ID3, ID3NoHeaderError, TALB, TDRC, TIT2, TPE1, TPE2, TRCK, TXXX, WOAS,
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
            info = ydl.extract_info(url, download=False)
        _ensure_channel(info)
        return info
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
            info = ydl.extract_info(url, download=True)
        _ensure_channel(info)
        return info

    return await run_blocking(blocking_download)


# Bump the version whenever tagging rules change so cached files get re-tagged.
TAGGER_MARKER = 'mp3-uploader'
TAGGER_VERSION = '2'


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


def _normalize(name: str) -> str:
    return ''.join(ch for ch in name.casefold() if ch.isalnum())


def _channel_core(channel: str) -> str:
    """Channel name without well-known decorations: ' - Topic', 'VEVO', 'Official'."""
    core = _clean_artist(channel) or ''
    for suffix in ('vevo', 'official'):
        if core.casefold().endswith(suffix) and len(core) > len(suffix):
            core = core[:-len(suffix)]
    return core


def _fetch_channel(url: str) -> str | None:
    """Channel name via YouTube oEmbed; used when yt-dlp could not read the watch page."""
    try:
        query = urlencode({'url': url, 'format': 'json'})
        with urlopen(f'https://www.youtube.com/oembed?{query}', timeout=10) as response:
            return json.load(response).get('author_name')
    except Exception as e:
        logger.info(f'[_fetch_channel] oEmbed failed for {url}: {e}')
        return None


def _ensure_channel(info: dict | None):
    if info and info.get('_type', 'video') == 'video' and not (info.get('uploader') or info.get('channel')):
        url = info.get('webpage_url') or (info.get('id') and get_url_by_v_id(info['id']))
        if url:
            info['uploader'] = _fetch_channel(url)


# Exact, case-insensitive suffixes YouTube channels append to music videos.
# A fixed list instead of a regex, so a real title is never cut by a guess.
_TITLE_NOISE = {
    f'{open_}{label}{close}'
    for open_, close in (('(', ')'), ('[', ']'))
    for label in (
        'official video', 'official music video', 'official audio', 'official lyric video',
        'official lyrics video', 'official visualizer', 'official visualiser', 'lyric video',
        'lyrics video', 'lyrics', 'visualizer', 'visualiser', 'audio', 'official', 'music video',
        'official hd video', 'hd', '4k', 'official 4k video',
    )
}


def _strip_noise(title: str) -> str:
    cleaned = title.strip()
    changed = True
    while changed:
        changed = False
        for noise in _TITLE_NOISE:
            if cleaned.lower().endswith(noise) and len(cleaned) > len(noise):
                cleaned = cleaned[:-len(noise)].rstrip()
                changed = True
    return cleaned


def _split_artist_prefix(title: str, channel: str | None) -> tuple[str | None, str]:
    """Split 'Artist - Song' only when 'Artist' is the channel's own name.

    Names are compared ignoring case, spaces and punctuation, so 'FrostChildrenVEVO'
    matches 'Frost Children'. Anything else is left untouched.
    """
    if not channel:
        return None, title
    core = _normalize(_channel_core(channel))
    if not core:
        return None, title
    for sep in (' - ', ' – ', ' — '):
        prefix, found, rest = title.partition(sep)
        if found and rest.strip() and _normalize(prefix) == core:
            return prefix.strip(), rest.strip()
    return None, title


def meta_from_info(info: dict) -> TrackMeta:
    """Prefer YouTube Music fields (track/artist/album) over generic video fields."""
    channel = info.get('uploader') or info.get('channel')
    artist = info.get('artist') or info.get('creator')
    track = info.get('track')

    if track:
        title = track
    else:
        raw = info.get('title') or info.get('id') or 'Unknown'
        prefix_artist, title = _split_artist_prefix(_strip_noise(raw), artist or channel)
        title = title or raw
        # The artist as spelled in the title beats 'FrostChildrenVEVO'.
        artist = artist or prefix_artist

    artist = artist or _clean_artist(channel) or 'Unknown'
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


def display_filename(meta: TrackMeta | None) -> str | None:
    if meta is None:
        return None
    name = meta.title if meta.artist in (None, '', 'Unknown') else f'{meta.artist} - {meta.title}'
    return f"{name.replace('/', '_')}.mp3"


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

    tags.setall(f'TXXX:{TAGGER_MARKER}', [TXXX(encoding=3, desc=TAGGER_MARKER, text=TAGGER_VERSION)])
    tags.save(mp3_path, v2_version=3)


def is_tagged(mp3_path: str) -> bool:
    """True if the file was tagged by the current tagging logic (not by older code)."""
    try:
        frame = ID3(mp3_path).get(f'TXXX:{TAGGER_MARKER}')
    except ID3NoHeaderError:
        return False
    return bool(frame) and frame.text[0] == TAGGER_VERSION


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
    """Embed a 600px square cover and tags into the MP3; no separate image is kept."""
    def blocking():
        src = _find_thumbnail(path)
        cover = f'{path}.cover.jpg'
        if src:
            _square_jpeg(src, cover, 600)
            os.remove(src)
        write_tags(f'{path}.mp3', meta, cover if os.path.isfile(cover) else None)
        if os.path.isfile(cover):
            os.remove(cover)

    await run_blocking(blocking)


async def make_thumbnail(mp3_path: str) -> bytes | None:
    """Build a 320x320 JPEG from the embedded cover in memory.

    The Bot API does not read cover art from the file itself, so the thumbnail
    has to be sent explicitly; it is never stored on disk.
    """
    def blocking():
        try:
            covers = ID3(mp3_path).getall('APIC')
        except ID3NoHeaderError:
            return None
        if not covers:
            return None
        result = subprocess.run(
            [
                'ffmpeg', '-loglevel', 'error', '-i', 'pipe:0',
                '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=320:320",
                '-q:v', '4', '-f', 'mjpeg', 'pipe:1',
            ],
            input=covers[0].data,
            capture_output=True,
        )
        return result.stdout or None

    return await run_blocking(blocking)


async def upgrade_legacy(path: str, url: str):
    """Bring a cached MP3 made by older code up to date.

    Embeds a leftover .jpg cover and, if the file lacks current tags, re-reads
    the video info (no download) and re-tags it.
    """
    mp3 = f'{path}.mp3'
    legacy = f'{path}.jpg'
    if not os.path.isfile(mp3):
        return

    def embed_legacy_cover():
        try:
            tags = ID3(mp3)
        except ID3NoHeaderError:
            tags = ID3()
        if not tags.getall('APIC'):
            with open(legacy, 'rb') as f:
                tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=f.read()))
            tags.save(mp3, v2_version=3)
        os.remove(legacy)

    if os.path.isfile(legacy):
        await run_blocking(embed_legacy_cover)

    if not is_tagged(mp3):
        try:
            info = await get_info(url)
        except Exception as e:
            logger.info(f'[upgrade_legacy] could not re-tag {mp3}: {e}')
            return
        meta = meta_from_info(info)
        # Existing APIC is kept: write_tags only replaces frames it is given.
        await run_blocking(lambda: write_tags(mp3, meta))


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
