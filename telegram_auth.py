import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitData(ValueError):
    pass


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 3600,
    now: int | None = None,
) -> dict:
    if not init_data or len(init_data) > 16_384:
        raise InvalidInitData("Missing or oversized initData")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise InvalidInitData("Malformed initData") from exc

    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InvalidInitData("Duplicate initData fields")

    received_hash = fields.get("hash", "")
    if len(received_hash) != 64:
        raise InvalidInitData("Missing or malformed initData hash")

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
        if key != "hash"
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash.lower()):
        raise InvalidInitData("Invalid initData signature")

    try:
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidInitData("Missing or malformed user/auth_date") from exc

    current_time = int(time.time()) if now is None else now
    if auth_date > current_time + 30:
        raise InvalidInitData("initData timestamp is in the future")
    if current_time - auth_date > max_age_seconds:
        raise InvalidInitData("initData has expired")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user["id"] <= 0:
        raise InvalidInitData("Invalid Telegram user")

    return user
