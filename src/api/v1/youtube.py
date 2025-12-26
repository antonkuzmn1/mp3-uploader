import math
import os

from fastapi import APIRouter, HTTPException
from starlette import status

from src import utils, logger, config
from src.api.schemas import YouTubeRequest
from src.utils import download_audio, convert_thumbnail


router = APIRouter(prefix='/v1/youtube', tags=['YouTube'])


@router.post('/')
async def upload_youtube(data: YouTubeRequest):
    logger.info(f'[upload_youtube] Requested Video ID: {data.url}')
    video_id = utils.get_id_from_url(data.url)

    if video_id is None:
        msg_base = f'Incorrect YT URL link: {data.url}'
        msg = f'{msg_base}\n\nexample: https://www.youtube.com/watch?v=VIDEO_ID'
        logger.info(f'[upload_youtube] {video_id}: {msg_base}')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    path = f'{config.STORAGE_DIR}/{video_id}'
    successfully_response = {
        'status': 'ok',
        'result': f'{config.MP3_STORAGE_URL}{video_id}.mp3',
        'thumbnail': f'{config.MP3_STORAGE_URL}{video_id}.jpg',
    }
    if os.path.isfile(f'{path}.mp3') and os.path.isfile(f'{path}.jpg'):
        logger.info(f'[upload_youtube] Return: {video_id}.mp3')
        return successfully_response

    logger.info(f'[upload_youtube] {video_id}: downloading...')
    try:
        info = await download_audio(data.url, path)
    except ValueError as e:
        msg = str(e)
        if msg == 'Video is longer than 1 hour':
            logger.info(f'[upload_youtube] {video_id}: {msg}')
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=msg)
        if msg == 'The video`s length could not be determined, but it may be a live broadcast':
            logger.info(f'[upload_youtube] {video_id}: {msg}')
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=msg)
        raise e

    title = info.get('title')
    uploader = info.get('uploader')

    logger.info(f'[upload_youtube] {video_id}: converting...')
    await convert_thumbnail(path, title, uploader)

    file_size_mb = os.path.getsize(f'{path}.mp3') / 1024 / 1024
    if file_size_mb > 48:
        msg = f'file "{title}" too big ({math.floor(file_size_mb)}MB > 48MB)'
        logger.info(f'[upload_youtube] {video_id}: {msg}')
        if os.path.isfile(f'{path}.mp3'):
            os.remove(f'{path}.mp3')
        if os.path.isfile(f'{path}.jpg'):
            os.remove(f'{path}.jpg')
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=msg)

    logger.info(f'[upload_youtube] Return: {video_id}.mp3')
    return successfully_response