import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING

from bot import dispatcher
from config import Settings, get_frontend_origins, load_settings
from schemas import GameCreate, GameResponse
from telegram_auth import InvalidInitData, validate_init_data
from users import upsert_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_frontend_origins = get_frontend_origins()


def game_to_response(game: dict[str, Any]) -> GameResponse:
    return GameResponse(
        id=str(game["_id"]),
        title=game["title"],
        description=game["description"],
        launch_url=game["launch_url"],
        thumbnail_url=game.get("thumbnail_url"),
        creator_id=game["creator_id"],
        creator_username=game.get("creator_username"),
        created_at=game["created_at"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    bot = Bot(settings.bot_token)
    mongo_client = AsyncIOMotorClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )
    polling_task: asyncio.Task | None = None

    try:
        await mongo_client.admin.command("ping")
        database = mongo_client[settings.database_name]
        await database.games.create_index([("created_at", DESCENDING)])
        await database.users.create_index([("last_seen_at", DESCENDING)])

        # Fail startup rather than serving an unusable bot/API configuration.
        await bot.get_me()
        await bot.delete_webhook(drop_pending_updates=False)

        app.state.settings = settings
        app.state.database = database
        polling_task = asyncio.create_task(
            dispatcher.start_polling(
                bot,
                handle_signals=False,
                close_bot_session=False,
                database=database,
                mini_app_url=settings.mini_app_url,
            ),
            name="telegram-long-polling",
        )

        def log_polling_failure(task: asyncio.Task) -> None:
            if task.cancelled():
                return
            error = task.exception()
            if error is not None:
                logger.error(
                    "Telegram polling stopped unexpectedly",
                    exc_info=(type(error), error, error.__traceback__),
                )
            else:
                logger.warning("Telegram polling stopped unexpectedly")

        polling_task.add_done_callback(log_polling_failure)
        yield
    finally:
        if polling_task is not None:
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        await bot.session.close()
        mongo_client.close()


app = FastAPI(title="Telegram Mini-Game Platform API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_frontend_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data"],
)


@app.middleware("http")
async def telegram_init_data_auth(request: Request, call_next):
    if request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        settings: Settings | None = getattr(request.app.state, "settings", None)
        if settings is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "Service is not ready"},
            )

        init_data = request.headers.get("X-Telegram-Init-Data", "")
        try:
            request.state.telegram_user = validate_init_data(
                init_data,
                settings.bot_token,
                settings.init_data_max_age_seconds,
            )
        except InvalidInitData as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": str(exc)},
            )

    return await call_next(request)


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/games", response_model=list[GameResponse])
async def list_games(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
) -> list[GameResponse]:
    user = request.state.telegram_user
    await upsert_user(
        request.app.state.database.users,
        user["id"],
        user.get("username"),
        user.get("first_name"),
    )
    documents = await (
        request.app.state.database.games.find({})
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    return [game_to_response(game) for game in documents]


@app.post("/api/publish", response_model=GameResponse, status_code=201)
async def publish_game(payload: GameCreate, request: Request) -> GameResponse:
    user = request.state.telegram_user
    database = request.app.state.database

    await upsert_user(
        database.users,
        user["id"],
        user.get("username"),
        user.get("first_name"),
    )

    document = {
        "title": payload.title,
        "description": payload.description,
        "launch_url": str(payload.launch_url),
        "thumbnail_url": (
            str(payload.thumbnail_url) if payload.thumbnail_url is not None else None
        ),
        "creator_id": user["id"],
        "creator_username": user.get("username"),
        "created_at": datetime.now(timezone.utc),
    }
    result = await database.games.insert_one(document)
    document["_id"] = result.inserted_id
    return game_to_response(document)
