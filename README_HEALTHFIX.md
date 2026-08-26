# v22 health fix

- `/health` is dependency-free and returns immediately for Render health checks.
- `/ready` checks PostgreSQL separately.
- Database initialization is moved to a background startup task and is also lazily guaranteed before DB-dependent requests.
- Telegram webhook registration is moved off the startup critical path.
