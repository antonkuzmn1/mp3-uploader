import math
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, HTTPException, File
from starlette import status

from src import logger, config

router = APIRouter(prefix='/v1/mp3', tags=['MP3'])


@router.post('/')
async def upload_mp3(file: UploadFile = File(...)):
    logger.info(f'[upload_mp3] Start uploading: {file.filename}')

    if not file.filename.endswith('.mp3'):
        msg = 'File type not supported'
        raise HTTPException(status_code=status.HTTP_415, detail=msg)

    file_size_mb = file.size / 1024 / 1024
    if file_size_mb > 48:
        msg = f'file "{file.filename}" too big ({math.floor(file_size_mb)}MB > 48MB)'
        logger.info(f'[upload_mp3] Return: {msg}')
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=msg)

    file_id = str(uuid.uuid4())
    path = Path(config.STORAGE_DIR) / f'{file_id}.mp3'
    successfully_response = {'status': 'ok', 'result': f'{config.MP3_STORAGE_URL}{file_id}.mp3'}
    if path.is_file():
        logger.info(f'[upload_mp3] Return: {file_id}.mp3')
        return successfully_response

    with path.open('wb') as f:
        f.write(file.file.read())

    return successfully_response