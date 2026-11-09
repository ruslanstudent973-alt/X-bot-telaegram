import logging
from typing import Any

from aiogram import Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from users import upsert_user

logger = logging.getLogger(__name__)
router = Router()
dispatcher = Dispatcher()
dispatcher.include_router(router)


@router.message(CommandStart())
async def start_command(
    message: Message,
    database: Any,
    mini_app_url: str,
) -> None:
    user = message.from_user
    if user is None:
        logger.warning("Received /start without Telegram user details")
        return

    await upsert_user(database.users, user.id, user.username, user.first_name)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open game library",
                    web_app=WebAppInfo(url=mini_app_url),
                )
            ]
        ]
    )
    await message.answer(
        "Welcome! Discover and play community-made mini-games.",
        reply_markup=keyboard,
    )
