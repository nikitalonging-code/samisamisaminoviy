# NFT Gift v43

Fixes for new-repository deployments: dynamic Render service URLs, automatic Telegram webhook registration using RENDER_EXTERNAL_URL, webhook diagnostics, and modal stacking fixes so Crash betting/promo top-ups render above the active game.

Required backend env: BOT_TOKEN, BOT_USERNAME, ADMIN_IDS, DATABASE_URL, WORKER_SECRET. Render blueprint now wires FRONTEND_PUBLIC_URL/BACKEND_URL/API_URL from each service external URL.
