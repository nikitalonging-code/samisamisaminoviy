# V60 Rocket gameplay fix

- Rocket animation uses the supplied transparent WebM/MP4 and is hidden during the server countdown.
- When the crash round changes from `waiting` to `flying`, the rocket video starts; playback speed is adjusted to fit the calculated crash duration.
- The rocket controls (bet/cashout) are placed directly under the rocket stage, always visible without scrolling; the bets list is the scrollable area.
- The crash screen is driven by `/api/crash/current`, so the displayed round, countdown, bets and cashout state stay synced to the backend.
- Bet button accepts new balance bets only during the server `waiting` phase; bets are written to `crash_bets` and shown immediately in the current-round live list.
