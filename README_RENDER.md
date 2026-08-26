# Render deployment — updated MVP

This archive includes:
- the supplied `ice_arena_modified.html` as the frontend;
- rocket controls kept visible with sticky positioning on mobile/WebView;
- upgrade wheel/result fixed so the visual landing and success/failure outcome use the same deterministic landing rule;
- `backend/gift_catalog.json` with 118 gift collections extracted from the supplied frontend;
- PostgreSQL `gift_catalog` table seeded automatically by the backend;
- `/api/catalog` endpoint;
- existing backend/worker/Render configuration.

The 118 catalog entries are the collections present in the supplied HTML, not a claim that this is every collectible Telegram gift ever issued.


## MRKT token без ручной ротации

MRKT теперь авторизуется автоматически через Telegram user-session worker. `MRKT_AUTH_TOKEN` больше не нужен для обычной работы. На Render backend вызывает защищённый endpoint worker-а, worker через Telethon открывает MRKT Mini App, получает свежий `tgWebAppData` и обменивает его на MRKT token. Токен кэшируется на 6 часов и обновляется автоматически; при ответе MRKT 401/403 backend принудительно получает новый токен.

Нужно один раз настроить на worker: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`, а также `WORKER_SECRET`. Тот же `WORKER_SECRET` должен быть указан у backend. `MRKT_WORKER_URL` в Blueprint уже указывает на `https://nft-gift-worker.onrender.com`.

## TON Connect
Set backend environment variable `TON_DEPOSIT_WALLET` to the app deposit wallet address.
