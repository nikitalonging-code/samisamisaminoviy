# NFT Gift v17

## Ice Arena
- True shared PvP pool based on the source Ice Arena.
- First player occupies 100% of the field.
- Each later stake repartitions the entire field by stake share.
- When the second player joins, a 20-second countdown starts at the top of the arena.
- After the countdown, the label becomes "Шар на поле" and the puck animation begins.
- The puck stays hidden before the round starts.

## Referrals
- Referral link is a Telegram bot deep link: `https://t.me/<BOT_USERNAME>?start=ref_<code>`.
- The backend also exposes `POST /telegram/webhook` to convert `/start ref_<code>` into a Mini App button preserving the referral code.
- With `AUTO_SET_WEBHOOK=1` (default) and `APP_URL` set, the backend registers this webhook on startup.

## Required Render variables on backend
- BOT_TOKEN
- BOT_USERNAME
- APP_URL (frontend URL)
- AUTO_SET_WEBHOOK=1
