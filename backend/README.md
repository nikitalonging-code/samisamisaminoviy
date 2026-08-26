# NFT Gift MVP backend

Минимальный backend для связки Mini App ↔ Telegram worker.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export WORKER_SECRET=dev-secret
uvicorn main:app --reload --port 8080
```

В MVP авторизация Mini App упрощена до заголовка `X-Telegram-User-Id`.
В продакшене его нужно заменить на серверную проверку Telegram Mini App `initData`.

MRKT больше не требует ручной ежедневной ротации токена: backend обращается к Telegram user-session worker, который сам открывает MRKT Mini App, получает свежий `tgWebAppData`, обменивает его на MRKT token и кэширует токен на несколько часов. `MRKT_AUTH_TOKEN` оставлен только как аварийный fallback.

## API

- `GET /health`
- `GET /api/me`
- `GET /api/inventory`
- `POST /api/withdrawals`
- `GET /api/withdrawals`
- `POST /api/internal/gifts` — внутренний endpoint для worker.

## Что намеренно не входит

1. Реальная автоматизация Portals — только интерфейс адаптера/очереди.
2. Реальная обработка Telegram session — вынесена в отдельный worker.
3. Продовая авторизация/Rate limit/anti-fraud.


Gift catalog: `gift_catalog.json` is seeded into PostgreSQL table `gift_catalog` on backend startup; source contains 118 collections from the supplied frontend.
