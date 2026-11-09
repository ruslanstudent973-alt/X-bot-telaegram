import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    mongo_uri: str
    database_name: str
    mini_app_url: str
    frontend_origins: tuple[str, ...]
    init_data_max_age_seconds: int


def get_frontend_origins() -> tuple[str, ...]:
    configured_origins = tuple(
        origin.strip().rstrip("/")
        for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    )
    mini_app_url = urlparse(os.getenv("MINI_APP_URL", ""))
    origins = configured_origins or (
        (f"{mini_app_url.scheme}://{mini_app_url.netloc}",)
        if mini_app_url.scheme and mini_app_url.netloc
        else ()
    )
    for origin in origins:
        parsed = urlparse(origin)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise RuntimeError(
                "FRONTEND_ORIGINS must contain only absolute HTTPS origins"
            )
    return origins


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    mongo_uri = os.getenv("MONGODB_URI", "").strip()
    mini_app_url = os.getenv("MINI_APP_URL", "").strip()
    database_name = os.getenv("MONGODB_DATABASE", "telegram_games").strip()

    if not bot_token:
        raise RuntimeError("BOT_TOKEN must be configured")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI must be configured")
    if not database_name:
        raise RuntimeError("MONGODB_DATABASE cannot be empty")

    parsed_mini_app_url = urlparse(mini_app_url)
    if (
        parsed_mini_app_url.scheme != "https"
        or not parsed_mini_app_url.netloc
        or parsed_mini_app_url.username
        or parsed_mini_app_url.password
    ):
        raise RuntimeError("MINI_APP_URL must be an absolute HTTPS URL")
    frontend_origins = get_frontend_origins()

    try:
        max_age = int(os.getenv("INIT_DATA_MAX_AGE_SECONDS", "3600"))
    except ValueError as exc:
        raise RuntimeError("INIT_DATA_MAX_AGE_SECONDS must be an integer") from exc
    if max_age <= 0:
        raise RuntimeError("INIT_DATA_MAX_AGE_SECONDS must be greater than zero")

    return Settings(
        bot_token=bot_token,
        mongo_uri=mongo_uri,
        database_name=database_name,
        mini_app_url=mini_app_url,
        frontend_origins=frontend_origins,
        init_data_max_age_seconds=max_age,
    )
