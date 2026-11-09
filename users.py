from datetime import datetime, timezone
from typing import Any


async def upsert_user(
    users: Any,
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> None:
    now = datetime.now(timezone.utc)
    await users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_seen_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
