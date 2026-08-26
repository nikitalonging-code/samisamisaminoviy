# v26 gate fix

Maintenance gate now validates Telegram WebApp initData on the backend, so admins are recognized by their real Telegram ID. The frontend waits for Telegram identity before calling /api/config. Both index.html and app.html use the same gate logic.
