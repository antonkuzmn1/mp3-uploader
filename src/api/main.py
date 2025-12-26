from contextlib import asynccontextmanager
from urllib.request import Request

from fastapi import FastAPI, APIRouter
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src import logger
from src.api.v1 import youtube_router, mp3_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix='/api')
router.include_router(youtube_router)
router.include_router(mp3_router)
app.include_router(router)


@app.exception_handler(Exception)
async def all_exception_handler(_req: Request, exc: Exception):
    logger.error(str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'detail': 'Internal Server Error'},
    )


@app.get("/")
async def main():
    return {
        "message": "test!",
        "test": 1,
    }