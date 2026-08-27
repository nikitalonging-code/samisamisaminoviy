# NFT Gift MVP v8

Чистая версия для Render: frontend / backend / worker в корне.

## Render secrets

Backend:
- `DATABASE_URL` — существующая PostgreSQL база
- `BOT_USERNAME` — username Telegram-бота без `@`
- `BOT_TOKEN` — токен Telegram-бота
- `ADMIN_IDS` — Telegram ID админов через запятую
- `WORKER_SECRET` — берётся из worker
- `MRKT_WORKER_URL` — URL worker

Worker:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION`
- `WORKER_SECRET`

## Что есть

- Live-лента сверху интерфейса с реальными событиями Crash / Cases.
- Telegram NFT-подарки используются как визуалы режимов и кейсов.
- Ice Arena доступна из PvP, а не из Play Hub; два отдельных игрока занимают два поля.
- Реферальная ссылка через `startapp=ref_<code>` и Telegram share chooser.
- Реферальная премия 10% от депозитов приглашённого.
- Задания и рейтинг по обороту TON.
- Отправить подарок открывает `@chibiop`.
- Админ-панель только для `ADMIN_IDS`: статистика, баланс, NFT, рассылка, бан/разбан, режим закрытого приложения.
- Закрытый режим показывает обычным пользователям бесконечный экран загрузки; админов пропускает.
- Avatar fallback через Telegram Bot API, если прямой `photo_url` не загрузился.
