from src.api.v1.youtube import router as youtube_router
from src.api.v1.mp3 import router as mp3_router

__all__ = [
    'youtube_router',
    'mp3_router',
]