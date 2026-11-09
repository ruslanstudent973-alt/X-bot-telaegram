# Telegram Mini-Game Platform Backend

FastAPI serves the Mini App API and health check, Aiogram handles bot updates
using long polling, and MongoDB stores users and published game metadata.

## Project layout

```text
.
├── bot.py               # /start handler and Mini App launch button
├── config.py            # Environment configuration
├── main.py              # FastAPI app, auth middleware, API and lifecycle
├── schemas.py           # Request/response validation
├── telegram_auth.py     # Telegram WebApp initData verification
├── users.py             # Shared MongoDB user upsert
├── requirements.txt
├── render.yaml
└── .env.example
```

## Run locally

1. Use Python 3.12 and create/activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `BOT_TOKEN`, `MONGODB_URI`, and
   `MINI_APP_URL`. The Mini App URL must be HTTPS.
4. Run `uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
5. In BotFather, configure the bot's Mini App domain to match the host in
   `MINI_APP_URL`.

The application validates its MongoDB connection and bot token on startup.
The bot uses long polling, so run exactly one application instance for a bot
token; do not enable multiple web-service replicas without switching the bot
to a webhook architecture.

## API

All `/api/*` routes require a fresh `initData` string from
`Telegram.WebApp.initData`. Send it exactly as provided in the
`X-Telegram-Init-Data` header; do not trust `initDataUnsafe` or a client-supplied
user ID. The server verifies Telegram's HMAC signature and timestamp before
processing a request. The default accepted age is one hour and can be changed
with `INIT_DATA_MAX_AGE_SECONDS`.

- `GET /api/games?limit=30&skip=0` — newest games, with bounded pagination.
- `POST /api/publish` — publish a game. JSON body:

  ```json
  {
    "title": "My Mini-Game",
    "description": "A short description",
    "launch_url": "https://games.example.com/my-game",
    "thumbnail_url": "https://games.example.com/my-game.png"
  }
  ```

  `thumbnail_url` is optional. Game launch and thumbnail URLs must use HTTPS.
- `GET /ping` — Render health check; returns `{"status":"ok"}`.

Example frontend request:

```javascript
const response = await fetch(`${API_BASE_URL}/api/games`, {
  headers: { "X-Telegram-Init-Data": window.Telegram.WebApp.initData }
});
```

## Deploy to Render

1. Create a MongoDB database (for example, MongoDB Atlas) and allow network
   access from Render. Use a least-privilege database user.
2. Push this project to a Git repository and create a Render Web Service from it
   (or use the included `render.yaml` Blueprint).
3. Set these environment variables in Render:
   - `BOT_TOKEN`: token from BotFather.
   - `MONGODB_URI`: MongoDB connection string.
   - `MONGODB_DATABASE`: database name (defaults to `telegram_games`).
   - `MINI_APP_URL`: public HTTPS URL of the Mini App frontend.
   - `FRONTEND_ORIGINS`: optional comma-separated HTTPS browser origins if the
     frontend uses a different origin from `MINI_APP_URL`.
   - `INIT_DATA_MAX_AGE_SECONDS`: optional; defaults to `3600`.
4. Set the Render service **Start Command** to:

   ```sh
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

5. Set the service health-check path to `/ping`, and configure the Mini App
   domain with BotFather.

`/ping` is for health monitoring and can be polled by Render or an uptime
monitor. It does not keep a suspended instance awake. For 24/7 availability,
use a Render plan with always-on web services; a ping job is not a substitute
for an always-on plan. Keep a single service instance while using long polling.

## Production follow-ups

This backend deliberately stores only game metadata, not uploaded game files.
Before accepting community submissions at scale, add moderation/review,
ownership and update/delete flows, rate limits, abuse reporting, and a
controlled game-hosting/sandbox strategy. Never execute submitted game code on
the API server.
