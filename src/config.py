import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PERMITTED_IDS = {int(x) for x in os.getenv('TELEGRAM_BOT_PERMITTED_IDS').split(',') if x}

STORAGE_DIR = os.getenv('STORAGE_DIR')

MP3_STORAGE_URL = os.getenv('MP3_STORAGE_URL')