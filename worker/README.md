# Telegram worker

Это заготовка user-session worker на Telethon.

Он нужен для отдельной Telegram-сессии, чтобы принимать события и затем передавать нормализованные данные в backend.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполнить API_ID/API_HASH
python main.py
```

При первом запуске Telethon запросит авторизацию и создаст session-файл.

### Важно

Фактическая нормализация `StarGift` зависит от текущего Telegram MTProto layer и используемого клиента. Поэтому в этом MVP worker фиксирует событие, но сознательно не делает непроверенных предположений о полях подарка.

Для передачи collectible gift Telegram предоставляет `payments.transferStarGift`; если передача платная, используется invoice/payment flow. См. официальную документацию Telegram Gifts.


### Автоматическая авторизация MRKT

Worker теперь умеет сам получать MRKT API token через Telegram user session. Для этого нужны только `API_ID`, `API_HASH` и авторизованная `TELEGRAM_SESSION`/Telethon-сессия. Backend обращается к закрытому endpoint worker-а `/internal/mrkt/token`; токен не попадает во frontend. Worker кэширует его на `MRKT_TOKEN_CACHE_SECONDS` (по умолчанию 6 часов) и автоматически получает новый при истечении кэша. Если MRKT отвечает 401/403, backend принудительно запрашивает свежий токен и повторяет запрос.

Официальный Telegram API подтверждает, что `messages.requestAppWebView` возвращает URL WebView с пользовательскими данными Mini App, а документация MRKT описывает обмен `tgWebAppData` на токен через `/api/v1/auth`.
