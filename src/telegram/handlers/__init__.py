from .audio import router as audio_router
from .text import router as text_router
from .buttons import router as buttons_router

__all__ = [
    'audio_router',
    'text_router',
    'buttons_router',
]