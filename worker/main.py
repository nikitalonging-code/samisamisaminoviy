import os, asyncio, httpx, time
from urllib.parse import urlsplit, parse_qs, unquote
from dotenv import load_dotenv
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from fastapi import FastAPI, Header, HTTPException
import uvicorn

load_dotenv()
API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
SESSION_STRING = os.getenv('TELEGRAM_SESSION', '')
API_URL = os.getenv('API_URL', '')
WORKER_SECRET = os.getenv('WORKER_SECRET', '')
PORT = int(os.getenv('PORT', '10000'))

app = FastAPI()
client = None
mrkt_token = ''
mrkt_token_at = 0.0
mrkt_token_lock = asyncio.Lock()
MRKT_TOKEN_CACHE_SECONDS = int(os.getenv('MRKT_TOKEN_CACHE_SECONDS', '21600'))


async def _mint_mrkt_token():
    """Open MRKT's Telegram Mini App with the worker's user session and exchange
    the signed tgWebAppData for a short-lived MRKT API token.

    The token is never exposed to the browser; only the backend can request it.
    """
    global client
    if client is None or not client.is_connected():
        raise RuntimeError('Telegram client is not connected')

    bot = await client.get_entity('mrkt')
    bot_input_user = types.InputUser(user_id=bot.id, access_hash=bot.access_hash)
    app_ref = types.InputBotAppShortName(bot_id=bot_input_user, short_name='app')
    bot_app_result = await client(functions.messages.GetBotAppRequest(app=app_ref, hash=0))
    bot_app = bot_app_result.app

    if getattr(bot_app, 'inactive', False):
        raise RuntimeError('MRKT Mini App is inactive for the worker Telegram account')

    app = types.InputBotAppID(id=bot_app.id, access_hash=bot_app.access_hash)
    web_view = await client(functions.messages.RequestAppWebViewRequest(
        peer=bot,
        app=app,
        platform='android',
    ))

    fragment = urlsplit(web_view.url).fragment
    params = parse_qs(fragment, keep_blank_values=True)
    raw = params.get('tgWebAppData', [''])[0]
    if not raw:
        query = urlsplit(web_view.url).query
        raw = parse_qs(query, keep_blank_values=True).get('tgWebAppData', [''])[0]
    if not raw:
        raise RuntimeError('Telegram did not return tgWebAppData for MRKT')

    init_data = unquote(raw)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as http:
        response = await http.post(
            'https://api.tgmrkt.io/api/v1/auth',
            json={'data': init_data},
            headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'Referer': 'https://cdn.tgmrkt.io/'},
        )
        response.raise_for_status()
        data = response.json()

    token = str(data.get('token') or '').strip()
    if not token:
        raise RuntimeError(f'MRKT auth returned no token: {data}')
    return token


async def get_mrkt_token(force=False):
    global mrkt_token, mrkt_token_at
    async with mrkt_token_lock:
        now = time.time()
        if not force and mrkt_token and now - mrkt_token_at < MRKT_TOKEN_CACHE_SECONDS:
            return mrkt_token
        mrkt_token = await _mint_mrkt_token()
        mrkt_token_at = now
        return mrkt_token


@app.get('/internal/mrkt/token')
async def internal_mrkt_token(x_worker_secret: str | None = Header(default=None), force: bool = False):
    if not WORKER_SECRET or x_worker_secret != WORKER_SECRET:
        raise HTTPException(403, 'Invalid worker secret')
    token = await get_mrkt_token(force=force)
    return {'token': token, 'cached': True, 'issued_at': int(mrkt_token_at)}

@app.get('/')
def health():
    return {'ok': True, 'service': 'telegram-worker'}

async def push_gift(owner_tg_id: int, gift: dict):
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(f'{API_URL}/api/internal/gifts', json={
            'owner_telegram_user_id': owner_tg_id,
            **gift,
        }, headers={'X-Worker-Secret': WORKER_SECRET})
        r.raise_for_status()
        return r.json()

async def on_new_message(event):
    action = getattr(event.message, 'action', None)
    if action is None:
        return
    cls = action.__class__.__name__.lower()
    if 'stargift' not in cls:
        return
    sender = await event.get_sender()
    owner_id = getattr(sender, 'id', None)
    if not owner_id:
        return
    print('Detected possible Star Gift event:', cls, 'owner=', owner_id)
    # TODO: normalize the exact Telegram gift fields for the current MTProto layer.

async def telegram_loop():
    global client
    if not API_ID or not API_HASH or not SESSION_STRING:
        raise RuntimeError('Set TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_SESSION')
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    @client.on(events.NewMessage)
    async def _on_new_message(event):
        await on_new_message(event)

    await client.start()
    me = await client.get_me()
    print(f'Worker logged in as @{getattr(me, "username", None)} / {me.id}')
    await client.run_until_disconnected()

async def serve():
    config = uvicorn.Config(app, host='0.0.0.0', port=PORT, log_level='info')
    server = uvicorn.Server(config)
    await asyncio.gather(server.serve(), telegram_loop())

if __name__ == '__main__':
    asyncio.run(serve())
