# v33 changes

- TON Connect deposits now create a server-side deposit intent and are credited to the internal balance after a matching on-chain inbound TON transaction is detected.
- Set `TON_DEPOSIT_WALLET` on the backend.
- Optional: set `TON_API_KEY` for higher TON Center API rate limits; without it, the public endpoint is used at its documented low request rate.
- Admin panel buttons are wired to the existing admin API endpoints.
- Frontend starts with zero/blank placeholders instead of the old demo `0.004` UI value, then synchronizes the real backend balance.
- Telegram `photo_url` is applied immediately on startup when available, then refreshed from `/api/me`.
- Balance sync polls `/api/me` every 2.5 seconds.
