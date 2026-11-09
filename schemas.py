from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class GameCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    launch_url: HttpUrl
    thumbnail_url: HttpUrl | None = None

    @field_validator("launch_url", "thumbnail_url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("URLs must use HTTPS")
        return value


class GameResponse(BaseModel):
    id: str
    title: str
    description: str
    launch_url: str
    thumbnail_url: str | None
    creator_id: int
    creator_username: str | None
    created_at: datetime
