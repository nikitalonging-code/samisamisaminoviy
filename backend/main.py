from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import os, re, time, uuid, json, random, urllib.request, urllib.error, urllib.parse, io, math, asyncio, threading, hashlib, hmac
import psycopg
from psycopg.rows import dict_row
from pathlib import Path

BASE = Path(__file__).resolve().parent
FRONTEND = BASE.parent / 'frontend' / 'index.html'
DATABASE_URL = os.getenv('DATABASE_URL', '')
MRKT_WORKER_URL = os.getenv('MRKT_WORKER_URL', '').rstrip('/')
MRKT_AUTH_TOKEN_FALLBACK = os.getenv('MRKT_AUTH_TOKEN', '').strip()
BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
BOT_USERNAME = os.getenv('BOT_USERNAME', '').strip().lstrip('@')
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '').strip().rstrip('/')
APP_URL = os.getenv('APP_URL', '').strip().rstrip('/') or os.getenv('FRONTEND_PUBLIC_URL', '').strip().rstrip('/')
BACKEND_URL = os.getenv('BACKEND_URL', 'https://nft-gift-backend-9krk.onrender.com').strip().rstrip('/')
_ADMIN_IDS_RAW = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = set(re.findall(r'\b\d{3,20}\b', _ADMIN_IDS_RAW))
MAINTENANCE_MESSAGE = os.getenv('MAINTENANCE_MESSAGE', 'Приложение временно закрыто на технические работы.')
TON_DEPOSIT_WALLET = os.getenv('TON_DEPOSIT_WALLET', '').strip()
TON_API_BASE = os.getenv('TON_API_BASE', 'https://toncenter.com/api/v2').rstrip('/')
TON_API_KEY = os.getenv('TON_API_KEY', '').strip()


app = FastAPI(title='NFT Gift MVP API', version='0.2.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

_DB_READY = False
_DB_INIT_LOCK = threading.Lock()

def _raw_db():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL is not configured')
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=4)

def db():
    global _DB_READY
    if not _DB_READY:
        with _DB_INIT_LOCK:
            if not _DB_READY:
                init_db()
                _DB_READY = True
    return _raw_db()



GIFT_CATALOG_PATH = BASE / 'gift_catalog.json'

def load_gift_catalog():
    try:
        return json.loads(GIFT_CATALOG_PATH.read_text(encoding='utf-8'))
    except Exception:
        return []

def init_db():
    global _DB_READY
    with _raw_db() as con:
        # Keep every SQL statement separate. Never put Python con.execute() calls
        # inside a triple-quoted SQL string.
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                telegram_user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                balance DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at BIGINT NOT NULL
            )
        """)
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT DEFAULT ''")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT DEFAULT ''")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT DEFAULT ''")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS balance DOUBLE PRECISION NOT NULL DEFAULT 0")

        con.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id),
                telegram_gift_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                model TEXT DEFAULT '',
                backdrop TEXT DEFAULT '',
                symbol TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                floor DOUBLE PRECISION DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'available',
                created_at BIGINT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id),
                inventory_id TEXT NOT NULL REFERENCES inventory(id),
                target_telegram_user_id BIGINT NOT NULL,
                gift_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                marketplace_order_id TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user_status ON inventory(user_id, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_withdrawals_user_created ON withdrawals(user_id, created_at DESC)")

        con.execute("""
            CREATE TABLE IF NOT EXISTS arena_matches (
                id UUID PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'waiting',
                start_at BIGINT,
                finish_at BIGINT,
                winner_user_id BIGINT,
                pool DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at BIGINT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS arena_players (
                id BIGSERIAL PRIMARY KEY,
                match_id UUID NOT NULL REFERENCES arena_matches(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL REFERENCES users(id),
                stake DOUBLE PRECISION NOT NULL,
                avatar_url TEXT DEFAULT '',
                display_name TEXT DEFAULT '',
                created_at BIGINT NOT NULL,
                UNIQUE(match_id, user_id)
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_arena_matches_status ON arena_matches(status, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_arena_players_match ON arena_players(match_id)")

        con.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                arena_bets INTEGER NOT NULL DEFAULT 0,
                arena_wins INTEGER NOT NULL DEFAULT 0,
                arena_volume DOUBLE PRECISION NOT NULL DEFAULT 0,
                arena_profit DOUBLE PRECISION NOT NULL DEFAULT 0,
                biggest_win DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at BIGINT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS gift_catalog (
                id BIGSERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                image_url TEXT DEFAULT '',
                floor DOUBLE PRECISION DEFAULT 0,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
        """)

        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code TEXT")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_earnings DOUBLE PRECISION NOT NULL DEFAULT 0")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_count INTEGER NOT NULL DEFAULT 0")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE")
        con.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT DEFAULT ''")
        con.execute("ALTER TABLE user_stats ADD COLUMN IF NOT EXISTS total_volume DOUBLE PRECISION NOT NULL DEFAULT 0")
        con.execute("""CREATE TABLE IF NOT EXISTS activity_log (id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,type TEXT NOT NULL,amount DOUBLE PRECISION NOT NULL DEFAULT 0,name TEXT DEFAULT '',image_url TEXT DEFAULT '',value DOUBLE PRECISION NOT NULL DEFAULT 0,kind TEXT DEFAULT '',action_text TEXT DEFAULT '',created_at BIGINT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS live_events (id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,username TEXT DEFAULT '',name TEXT DEFAULT '',image_url TEXT DEFAULT '',value DOUBLE PRECISION NOT NULL DEFAULT 0,kind TEXT DEFAULT '',action_text TEXT DEFAULT '',created_at BIGINT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')""")
        con.execute("INSERT INTO app_settings(key,value) VALUES('maintenance','0') ON CONFLICT (key) DO NOTHING")
        con.execute("""CREATE TABLE IF NOT EXISTS ton_deposits (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            wallet_address TEXT NOT NULL,
            amount_nano BIGINT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tx_hash TEXT UNIQUE,
            created_at BIGINT NOT NULL,
            confirmed_at BIGINT
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_ton_deposits_pending ON ton_deposits(status, created_at DESC)")
        con.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                max_uses INTEGER NOT NULL DEFAULT 0,
                used_count INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at BIGINT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS promo_redemptions (
                id BIGSERIAL PRIMARY KEY,
                code TEXT NOT NULL REFERENCES promo_codes(code) ON DELETE CASCADE,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                reward_kind TEXT NOT NULL,
                reward_name TEXT DEFAULT '',
                reward_value DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at BIGINT NOT NULL,
                UNIQUE(code, user_id)
            )
        """)

        catalog = load_gift_catalog()
        now = int(time.time())
        for gift in catalog:
            name = str(gift.get('name', '')).strip()
            if not name:
                continue
            image_url = str(gift.get('image_url', '') or '')
            floor = float(gift.get('floor') or 0)
            con.execute(
                """
                INSERT INTO gift_catalog(name, image_url, floor, created_at, updated_at)
                VALUES(%s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    image_url = EXCLUDED.image_url,
                    floor = CASE
                        WHEN EXCLUDED.floor > 0 THEN EXCLUDED.floor
                        ELSE gift_catalog.floor
                    END,
                    updated_at = EXCLUDED.updated_at
                """,
                (name, image_url, floor, now, now),
            )

class WithdrawalIn(BaseModel):
    inventory_id: str


@app.get('/api/catalog')
def gift_catalog():
    with db() as con:
        rows = con.execute('SELECT name, image_url, floor FROM gift_catalog ORDER BY name ASC').fetchall()
    return {'items': rows, 'count': len(rows)}

class GiftIn(BaseModel):
    owner_telegram_user_id: int
    telegram_gift_id: str
    name: str
    model: str = ''
    backdrop: str = ''
    symbol: str = ''
    image_url: str = ''
    floor: float = 0




def telegram_webapp_user(init_data: str):
    """Validate Telegram WebApp initData and return the embedded user dict."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
        supplied_hash = (parsed.get('hash') or [''])[0]
        if not supplied_hash:
            return None
        pairs=[]
        for k, vals in parsed.items():
            if k == 'hash':
                continue
            pairs.append(f"{k}={vals[0] if vals else ''}")
        data_check_string='\n'.join(sorted(pairs))
        secret_key=hmac.new(b'WebAppData', BOT_TOKEN.encode('utf-8'), hashlib.sha256).digest()
        calc=hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, supplied_hash):
            return None
        user_raw=(parsed.get('user') or [''])[0]
        return json.loads(user_raw) if user_raw else None
    except Exception:
        return None

def is_admin_telegram_id(tg_id: int) -> bool:
    return str(tg_id) in ADMIN_IDS


def require_admin(x_telegram_user_id: str | None):
    if not x_telegram_user_id:
        raise HTTPException(401, 'X-Telegram-User-Id required')
    try:
        tg_id = int(x_telegram_user_id)
    except ValueError:
        raise HTTPException(400, 'Invalid Telegram user id')
    if not is_admin_telegram_id(tg_id):
        raise HTTPException(403, 'Admin access required')
    return tg_id


def telegram_api(method: str, payload: dict):
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is not configured')
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/{method}'
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    if not data.get('ok'):
        raise RuntimeError(data.get('description') or 'Telegram API error')
    return data.get('result')



WITHDRAWAL_BACKDROP_FALLBACKS = ["Black", "Onyx Black", "Blue", "Purple", "Gold", "Emerald"]

def _notify_admins_withdrawal(user_row, item_row, withdrawal_id: str):
    if not BOT_TOKEN or not ADMIN_IDS:
        return
    backdrop = (item_row.get("backdrop") or "").strip() or random.choice(WITHDRAWAL_BACKDROP_FALLBACKS)
    username = user_row.get("username") or user_row.get("first_name") or "без username"
    text = (
        "📤 Новая заявка на вывод\n\n"
        f"Пользователь: @{username}\n"
        f"Подарок: {item_row.get('name') or 'NFT'}\n"
        f"Фон: {backdrop}\n"
        f"Withdrawal ID: {withdrawal_id}"
    )
    for admin_id in list(ADMIN_IDS):
        try:
            telegram_api('sendMessage', {'chat_id': int(admin_id), 'text': text})
        except Exception:
            pass


def enforce_access(u):
    if u.get('is_banned'):
        raise HTTPException(403, u.get('ban_reason') or 'Пользователь заблокирован')

    if u.get('is_banned'):
        raise HTTPException(403, u.get('ban_reason') or 'Пользователь заблокирован')


def current_user(x_telegram_user_id: str | None):
    if not x_telegram_user_id:
        raise HTTPException(401, 'X-Telegram-User-Id required in MVP mode')
    try:
        tg_id = int(x_telegram_user_id)
    except ValueError:
        raise HTTPException(400, 'Invalid Telegram user id')
    with db() as con:
        row = con.execute('SELECT * FROM users WHERE telegram_user_id=%s', (tg_id,)).fetchone()
        if not row:
            now = int(time.time())
            con.execute('INSERT INTO users(telegram_user_id, username, created_at, referral_code) VALUES(%s,%s,%s,%s) ON CONFLICT (telegram_user_id) DO NOTHING', (tg_id, '', now, str(tg_id)))
            row = con.execute('SELECT * FROM users WHERE telegram_user_id=%s', (tg_id,)).fetchone()
    enforce_access(row)
    return row

@app.get('/')
def home():
    return FileResponse(FRONTEND)

class ArenaJoinIn(BaseModel):
    amount: float


def arena_seed_value(seed: str) -> float:
    # Same tiny deterministic PRNG is mirrored in frontend so every client sees the same winner/path.
    h = 2166136261
    for b in str(seed).encode('utf-8'):
        h ^= b
        h = (h * 16777619) & 0xffffffff
    h ^= (h >> 13)
    h = (h * 2246822519) & 0xffffffff
    h ^= (h >> 16)
    return h / 4294967295.0

def arena_pick_winner(players, match_id):
    total = sum(float(p['stake']) for p in players)
    pick = arena_seed_value(str(match_id)) * total
    acc = 0.0
    for p in players:
        acc += float(p['stake'])
        if pick <= acc:
            return p
    return players[-1]

@app.get('/api/arena/current')
def arena_current(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    now = int(time.time())
    with db() as con:
        m = con.execute("SELECT * FROM arena_matches WHERE status IN ('waiting','countdown','running') ORDER BY created_at DESC LIMIT 1").fetchone()
        if not m:
            m = con.execute("SELECT * FROM arena_matches WHERE status='finished' AND finish_at >= %s ORDER BY finish_at DESC LIMIT 1", (now-12,)).fetchone()
        if not m:
            return {'match': None}
        players = con.execute('''SELECT p.user_id,p.stake,p.avatar_url,p.display_name,p.created_at,u.username
                                 FROM arena_players p JOIN users u ON u.id=p.user_id
                                 WHERE p.match_id=%s ORDER BY p.created_at ASC''',(m['id'],)).fetchall()
    return {'match': dict(m), 'players':[dict(p) for p in players], 'you_user_id':u['id']}


@app.post('/api/arena/join')
def arena_join(payload: ArenaJoinIn, x_telegram_user_id: str | None = Header(default=None)):
    amount = round(float(payload.amount), 6)
    if amount < 0.1:
        raise HTTPException(400, 'Минимальная ставка — 0.1 TON')
    u = current_user(x_telegram_user_id)
    now = int(time.time())
    with db() as con:
        ulock = con.execute('SELECT * FROM users WHERE id=%s FOR UPDATE', (u['id'],)).fetchone()
        if float(ulock['balance'] or 0) + 1e-9 < amount:
            raise HTTPException(400, 'Недостаточно TON на балансе')

        m = con.execute("SELECT * FROM arena_matches WHERE status IN ('waiting','countdown') ORDER BY created_at DESC LIMIT 1 FOR UPDATE").fetchone()
        if m and m['status']=='countdown' and m['start_at'] and now >= int(m['start_at']):
            raise HTTPException(409, 'Раунд уже стартовал')
        if not m:
            mid=uuid.uuid4()
            con.execute("INSERT INTO arena_matches(id,status,created_at,pool) VALUES(%s,'waiting',%s,0)", (mid,now))
            m=con.execute('SELECT * FROM arena_matches WHERE id=%s',(mid,)).fetchone()

        already=con.execute('SELECT 1 FROM arena_players WHERE match_id=%s AND user_id=%s LIMIT 1',(m['id'],u['id'])).fetchone()
        if already:
            raise HTTPException(409, 'Вы уже заняли поле в этом раунде')

        con.execute('UPDATE users SET balance=balance-%s WHERE id=%s',(amount,u['id']))
        name=(ulock['first_name'] or ulock['username'] or f'User {ulock["telegram_user_id"]}')[:64]
        con.execute('INSERT INTO arena_players(match_id,user_id,stake,avatar_url,display_name,created_at) VALUES(%s,%s,%s,%s,%s,%s)',
                    (m['id'],u['id'],amount,ulock['avatar_url'] or '',name,now))

        count=int(con.execute('SELECT COUNT(*) AS c FROM arena_players WHERE match_id=%s',(m['id'],)).fetchone()['c'])
        newpool=float(m['pool'] or 0)+amount
        if m['status']=='waiting' and count>=2:
            start_at=now+20
            con.execute("UPDATE arena_matches SET status='countdown', start_at=%s, pool=%s WHERE id=%s",(start_at,newpool,m['id']))
        else:
            con.execute('UPDATE arena_matches SET pool=%s WHERE id=%s',(newpool,m['id']))
        con.commit()
    return arena_current(x_telegram_user_id)


@app.post('/api/arena/resolve')
def arena_resolve(x_telegram_user_id: str | None = Header(default=None)):
    u=current_user(x_telegram_user_id)
    now=int(time.time())
    with db() as con:
        m=con.execute("SELECT * FROM arena_matches WHERE status='countdown' ORDER BY created_at DESC LIMIT 1 FOR UPDATE").fetchone()
        if not m:
            return arena_current(x_telegram_user_id)
        if not m['start_at'] or now < int(m['start_at']):
            return arena_current(x_telegram_user_id)
        players=con.execute('SELECT * FROM arena_players WHERE match_id=%s ORDER BY id ASC',(m['id'],)).fetchall()
        if len(players)<2:
            raise HTTPException(409,'Недостаточно игроков')

        total=sum(float(p['stake']) for p in players)
        winner=arena_pick_winner(players, m['id'])

        # 95% of the total pool goes to the winner; 5% is retained as app commission.
        payout=round(total * 0.95, 8)
        commission=round(total - payout, 8)
        con.execute('UPDATE users SET balance=balance+%s WHERE id=%s',(payout,winner['user_id']))
        for p in players:
            stats=con.execute('SELECT * FROM user_stats WHERE user_id=%s FOR UPDATE',(p['user_id'],)).fetchone()
            profit=(payout-float(p['stake'])) if p['user_id']==winner['user_id'] else -float(p['stake'])
            if not stats:
                con.execute('INSERT INTO user_stats(user_id,arena_bets,arena_wins,arena_volume,arena_profit,biggest_win,total_volume,updated_at) VALUES(%s,1,%s,%s,%s,%s,%s,%s)',
                            (p['user_id'],1 if p['user_id']==winner['user_id'] else 0,float(p['stake']),profit,max(0,profit),float(p['stake']),now))
            else:
                con.execute('''UPDATE user_stats SET arena_bets=arena_bets+1, arena_wins=arena_wins+%s, arena_volume=arena_volume+%s, arena_profit=arena_profit+%s, biggest_win=GREATEST(biggest_win,%s), total_volume=total_volume+%s, updated_at=%s WHERE user_id=%s''',
                            (1 if p['user_id']==winner['user_id'] else 0,float(p['stake']),profit,max(0,profit),float(p['stake']),now,p['user_id']))
        # Keep the displayed pool as the gross pool; commission is retained by the app.
        con.execute("UPDATE arena_matches SET status='finished',finish_at=%s,winner_user_id=%s,pool=%s WHERE id=%s",(now,winner['user_id'],total,m['id']))
        con.commit()
    return arena_current(x_telegram_user_id)


@app.get('/health')
def health():
    # Render health check must be dependency-free and return immediately.
    return {'ok': True}

@app.get('/ready')
def ready():
    # Deep readiness probe: verifies PostgreSQL separately from /health.
    try:
        with _raw_db() as con:
            con.execute('SELECT 1')
        return {'ok': True, 'db': True}
    except Exception as exc:
        return {'ok': False, 'db': False, 'error': str(exc)}

class ProfileIn(BaseModel):
    username: str = ''
    first_name: str = ''
    last_name: str = ''
    avatar_url: str = ''
    referral_code: str = ''

@app.get('/api/me')
def me(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        stats = con.execute('SELECT * FROM user_stats WHERE user_id=%s', (u['id'],)).fetchone()
    return {
        'telegram_user_id': u['telegram_user_id'], 'username': u['username'],
        'first_name': u['first_name'], 'last_name': u['last_name'],
        'avatar_url': u['avatar_url'], 'balance': float(u['balance'] or 0), 'is_admin': is_admin_telegram_id(int(u['telegram_user_id'])),
        'stats': dict(stats) if stats else {'arena_bets':0,'arena_wins':0,'arena_volume':0,'arena_profit':0,'biggest_win':0,'total_volume':0}
    }

@app.post('/api/profile')
def update_profile(payload: ProfileIn, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        con.execute('UPDATE users SET username=%s, first_name=%s, last_name=%s, avatar_url=%s, referral_code=COALESCE(referral_code,%s) WHERE id=%s',
                    (payload.username[:64], payload.first_name[:64], payload.last_name[:64], payload.avatar_url[:500], str(u['telegram_user_id']), u['id']))
        code=(payload.referral_code or '').strip()
        if code.startswith('ref_'): code=code[4:]
        if code.isdigit() and int(code) != int(u['telegram_user_id']):
            ref=con.execute('SELECT id FROM users WHERE telegram_user_id=%s',(int(code),)).fetchone()
            if ref and not u.get('referred_by'):
                con.execute('UPDATE users SET referred_by=%s WHERE id=%s AND referred_by IS NULL',(ref['id'],u['id']))
                con.execute('UPDATE users SET referral_count=referral_count+1 WHERE id=%s',(ref['id'],))
    return me(x_telegram_user_id)

@app.get('/api/balance')
def balance(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    return {'balance': float(u['balance'] or 0)}

@app.get('/api/inventory')
def inventory(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        rows = con.execute("SELECT * FROM inventory WHERE user_id=%s AND status='available' ORDER BY created_at DESC", (u['id'],)).fetchall()
    return {'items': rows}

@app.post('/api/internal/gifts')
def add_gift(payload: GiftIn, x_worker_secret: str | None = Header(default=None)):
    secret = os.getenv('WORKER_SECRET', '')
    if not secret or x_worker_secret != secret:
        raise HTTPException(403, 'Invalid worker secret')
    with db() as con:
        u = con.execute('SELECT * FROM users WHERE telegram_user_id=%s', (payload.owner_telegram_user_id,)).fetchone()
        if not u:
            now = int(time.time())
            con.execute('INSERT INTO users(telegram_user_id, username, created_at) VALUES(%s,%s,%s)', (payload.owner_telegram_user_id, '', now))
            u = con.execute('SELECT * FROM users WHERE telegram_user_id=%s', (payload.owner_telegram_user_id,)).fetchone()
        existing = con.execute('SELECT id FROM inventory WHERE telegram_gift_id=%s', (payload.telegram_gift_id,)).fetchone()
        if existing:
            return {'ok': True, 'duplicate': True, 'inventory_id': existing['id']}
        item_id = uuid.uuid4().hex
        con.execute('''INSERT INTO inventory
          (id,user_id,telegram_gift_id,name,model,backdrop,symbol,image_url,floor,status,created_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'available',%s)''',
          (item_id,u['id'],payload.telegram_gift_id,payload.name,payload.model,payload.backdrop,payload.symbol,payload.image_url,payload.floor,int(time.time())))
    return {'ok': True, 'inventory_id': item_id}

@app.post('/api/withdrawals')
def create_withdrawal(payload: WithdrawalIn, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        item = con.execute("SELECT * FROM inventory WHERE id=%s AND user_id=%s AND status='available' FOR UPDATE", (payload.inventory_id,u['id'])).fetchone()
        if not item:
            raise HTTPException(404, 'NFT not available')
        active = con.execute("SELECT id FROM withdrawals WHERE inventory_id=%s AND status IN ('pending','buying','bought','transferring')", (payload.inventory_id,)).fetchone()
        if active:
            raise HTTPException(409, 'Withdrawal already exists')
        wid = uuid.uuid4().hex
        now = int(time.time())
        con.execute("UPDATE inventory SET status='reserved' WHERE id=%s", (item['id'],))
        con.execute('''INSERT INTO withdrawals
          (id,user_id,inventory_id,target_telegram_user_id,gift_name,status,created_at,updated_at)
          VALUES(%s,%s,%s,%s,%s,'pending',%s,%s)''',
          (wid,u['id'],item['id'],u['telegram_user_id'],item['name'],now,now))
    threading.Thread(target=_notify_admins_withdrawal, args=(u, item, wid), daemon=True).start()
    return {'ok': True, 'withdrawal_id': wid, 'status': 'pending'}



class ActivityIn(BaseModel):
    type: str
    amount: float = 0
    name: str = ''
    image_url: str = ''
    value: float = 0
    kind: str = ''
    action_text: str = ''

@app.post('/api/activity')
def activity(payload: ActivityIn, x_telegram_user_id: str | None = Header(default=None)):
    u=current_user(x_telegram_user_id); now=int(time.time()); amount=max(0,float(payload.amount or 0))
    with db() as con:
        con.execute('INSERT INTO activity_log(user_id,type,amount,name,image_url,value,kind,action_text,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(u['id'],payload.type[:40],amount,payload.name[:120],payload.image_url[:500],float(payload.value or 0),payload.kind[:20],payload.action_text[:120],now))
        if amount>0:
            con.execute('INSERT INTO user_stats(user_id,total_volume,updated_at) VALUES(%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET total_volume=user_stats.total_volume+EXCLUDED.total_volume,updated_at=EXCLUDED.updated_at',(u['id'],amount,now))
        if payload.type in ('case_drop','crash_win'):
            con.execute('INSERT INTO live_events(user_id,username,name,image_url,value,kind,action_text,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(u['id'],u['username'] or u['first_name'] or '',payload.name[:120],payload.image_url[:500],float(payload.value or 0),payload.kind[:20],payload.action_text[:120],now))
    return {'ok':True}

class DepositIn(BaseModel):
    user_id: int
    amount: float
    tx_id: str = ''

@app.post('/api/internal/deposit')
def internal_deposit(payload: DepositIn, x_worker_secret: str | None = Header(default=None)):
    secret=os.getenv('WORKER_SECRET','')
    if not secret or x_worker_secret != secret: raise HTTPException(403,'Invalid worker secret')
    amount=round(float(payload.amount),6)
    if amount<=0: raise HTTPException(400,'Invalid deposit')
    with db() as con:
        u=con.execute('SELECT * FROM users WHERE id=%s FOR UPDATE',(payload.user_id,)).fetchone()
        if not u: raise HTTPException(404,'User not found')
        con.execute('UPDATE users SET balance=balance+%s WHERE id=%s',(amount,u['id']))
        if u.get('referred_by'):
            bonus=round(amount*0.10,6)
            con.execute('UPDATE users SET balance=balance+%s, referral_earnings=referral_earnings+%s WHERE id=%s',(bonus,bonus,u['referred_by']))
        con.execute("INSERT INTO activity_log(user_id,type,amount,name,created_at) VALUES(%s,'deposit',%s,'Deposit',%s)",(u['id'],amount,int(time.time())))
        return {'ok':True,'balance':float(u['balance'] or 0)+amount}

@app.get('/api/referral')
def referral(x_telegram_user_id: str | None = Header(default=None)):
    u=current_user(x_telegram_user_id)
    code=u.get('referral_code') or str(u['telegram_user_id'])
    ref_code=f'ref_{code}'
    encoded=urllib.parse.quote(ref_code, safe='')
    bot_link=f'https://t.me/{BOT_USERNAME}?start={encoded}' if BOT_USERNAME else ''
    mini_app_link=f'https://t.me/{BOT_USERNAME}?startapp={encoded}' if BOT_USERNAME else ''
    app_link=f'{APP_URL}/?ref={encoded}' if APP_URL else ''
    share_target=bot_link or mini_app_link or app_link
    return {
        'link': bot_link or share_target,
        'bot_link': bot_link,
        'mini_app_link': mini_app_link,
        'app_link': app_link,
        'share_url': 'https://t.me/share/url?url='+urllib.parse.quote(bot_link or share_target, safe='')+'&text='+urllib.parse.quote('Заходи в NFT Gift 🎁', safe=''),
        'ref_code': ref_code,
        'referrals': int(u.get('referral_count') or 0),
        'earned': float(u.get('referral_earnings') or 0)
    }

@app.get('/api/ping')
def ping():
    return {'ok': True, 'ts': int(time.time())}

@app.get('/telegram/webhook')
def telegram_webhook_info():
    if not BOT_TOKEN:
        return {'ok': False, 'error': 'BOT_TOKEN not configured'}
    try:
        info = telegram_api('getWebhookInfo', {})
        return {'ok': True, 'url': info.get('url',''), 'pending_update_count': info.get('pending_update_count',0), 'last_error_message': info.get('last_error_message','')}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}

@app.post('/telegram/webhook')
def telegram_webhook(update: dict):
    # /start and /start ref_CODE -> reply with a Mini App button.
    try:
        msg=update.get('message') or {}
        chat=msg.get('chat') or {}
        text=str(msg.get('text') or '').strip()
        if not chat.get('id'):
            return {'ok': True}
        cmd=text.split()[0] if text else ''
        if not cmd.startswith('/start'):
            return {'ok': True}
        parts=text.split(maxsplit=1)
        ref=parts[1].strip() if len(parts)>1 else ''
        ref=ref if ref.startswith('ref_') else ''
        url=APP_URL or ''
        if ref and url:
            url += '?ref=' + urllib.parse.quote(ref, safe='')
        if not url:
            telegram_api('sendMessage', {'chat_id':int(chat['id']), 'text':'Ссылка на приложение пока не настроена.'})
            return {'ok': True}
        keyboard={'inline_keyboard':[[{'text':'🎁 Открыть NFT Gift','web_app':{'url':url}}]]}
        text_out = 'Твоя реферальная ссылка активирована 🎁\nНажми кнопку ниже, чтобы открыть приложение.' if ref else 'Открывай NFT Gift по кнопке ниже 👇'
        telegram_api('sendMessage', {'chat_id':int(chat['id']), 'text':text_out, 'reply_markup':keyboard})
    except Exception as exc:
        print('telegram_webhook error:', repr(exc))
    return {'ok': True}

@app.on_event('startup')
async def background_bootstrap():
    async def _bootstrap():
        try:
            await asyncio.to_thread(init_db)
        except Exception:
            pass
        if os.getenv('AUTO_SET_WEBHOOK','1') == '1' and BOT_TOKEN:
            public_backend = (BACKEND_URL or RENDER_EXTERNAL_URL).rstrip('/')
            if public_backend:
                try:
                    await asyncio.to_thread(telegram_api, 'setWebhook', {
                        'url': f'{public_backend}/telegram/webhook',
                        'allowed_updates':['message'],
                        'drop_pending_updates': False,
                    })
                    info = await asyncio.to_thread(telegram_api, 'getWebhookInfo', {})
                    print('Telegram webhook:', info.get('url'), 'pending=', info.get('pending_update_count', 0))
                except Exception as exc:
                    print('Telegram webhook setup failed:', exc)
    asyncio.create_task(_bootstrap())

@app.get('/api/rating')
def rating(x_telegram_user_id: str | None = Header(default=None)):
    u=current_user(x_telegram_user_id)
    with db() as con:
        rows=con.execute("""SELECT u.id AS user_id,u.username,u.first_name,u.last_name,u.avatar_url,COALESCE(s.total_volume,0) AS volume FROM users u LEFT JOIN user_stats s ON s.user_id=u.id ORDER BY COALESCE(s.total_volume,0) DESC,u.created_at ASC LIMIT 100""").fetchall()
    return {'items':[dict(r) for r in rows],'you_user_id':u['id']}

@app.get('/api/tasks')
def tasks(x_telegram_user_id: str | None = Header(default=None)):
    u=current_user(x_telegram_user_id)
    with db() as con:
        stats=con.execute('SELECT * FROM user_stats WHERE user_id=%s',(u['id'],)).fetchone() or {'total_volume':0}
        rows=con.execute('SELECT type,COUNT(*) AS c,COALESCE(SUM(amount),0) AS s FROM activity_log WHERE user_id=%s GROUP BY type',(u['id'],)).fetchall()
    c={r['type']:(int(r['c']),float(r['s'] or 0)) for r in rows}
    items=[{'icon':'💳','title':'Внеси депозит от 1 TON','description':'Первый депозит не меньше 1 TON','progress':1 if c.get('deposit',(0,0))[1]>=1 else 0,'target':1,'reward':0.2},{'icon':'❄️','title':'Сделай 3 ставки в Ice Arena','description':'Три PvP-ставки','progress':c.get('arena_bet',(0,0))[0],'target':3,'reward':0.3},{'icon':'🚀','title':'Сделай 5 ставок в Crash','description':'Пять раундов Ракетки','progress':c.get('crash_bet',(0,0))[0],'target':5,'reward':0.2},{'icon':'🎁','title':'Открой 3 кейса','description':'Три любых кейса','progress':c.get('case_open',(0,0))[0],'target':3,'reward':0.5},{'icon':'👥','title':'Пригласи 3 друзей','description':'Друзья должны зайти по ссылке','progress':int(u.get('referral_count') or 0),'target':3,'reward':0.5},{'icon':'💎','title':'Сделай оборот 10 TON','description':'Суммарный оборот приложения','progress':float(stats.get('total_volume') or 0),'target':10,'reward':0.8}]
    for t in items:t['progress_label']=f"Готово · {t['target']}" if t['progress']>=t['target'] else (f"{t['progress']:.2f}/{t['target']}" if isinstance(t['progress'],float) else f"{t['progress']}/{t['target']}")
    return {'items':items}

@app.get('/api/live')
def live(x_telegram_user_id: str | None = Header(default=None)):
    current_user(x_telegram_user_id)
    with db() as con: rows=con.execute('SELECT * FROM live_events ORDER BY created_at DESC LIMIT 30').fetchall()
    return {'items':[dict(r) for r in rows]}


@app.get('/api/config')
def config(tg_id: str | None = None, x_telegram_user_id: str | None = Header(default=None), x_telegram_init_data: str | None = Header(default=None)):
    # App gate: prefer a cryptographically validated Telegram WebApp identity.
    tg_user = telegram_webapp_user(x_telegram_init_data or '')
    tg_id = None
    if tg_user and tg_user.get('id') is not None:
        tg_id = int(tg_user['id'])
    else:
        raw_id = tg_id or x_telegram_user_id
        try:
            tg_id=int(str(raw_id).strip()) if raw_id is not None else None
        except (ValueError, TypeError):
            tg_id=None
    if tg_id is None:
        raise HTTPException(401, 'Telegram identity required')
    username=(tg_user or {}).get('username','') or ''
    first_name=(tg_user or {}).get('first_name','') or ''
    with db() as con:
        u=con.execute('SELECT * FROM users WHERE telegram_user_id=%s',(tg_id,)).fetchone()
        if not u:
            now=int(time.time())
            con.execute(
                'INSERT INTO users(telegram_user_id, username, first_name, created_at, referral_code) VALUES(%s,%s,%s,%s,%s) ON CONFLICT (telegram_user_id) DO NOTHING',
                (tg_id,username,first_name,now,str(tg_id))
            )
            u=con.execute('SELECT * FROM users WHERE telegram_user_id=%s',(tg_id,)).fetchone()
    is_admin=is_admin_telegram_id(tg_id)
    if u.get('is_banned') and not is_admin:
        raise HTTPException(403, u.get('ban_reason') or 'Пользователь заблокирован')
    return {'maintenance': False, 'maintenance_message': '', 'is_admin': is_admin, 'bot_username': BOT_USERNAME, 'telegram_user_id': tg_id, 'username': username, 'ton_deposit_wallet': TON_DEPOSIT_WALLET}

@app.get('/api/admin-gate-check')
def admin_gate_check(tg_id: str | None = None, x_telegram_user_id: str | None = Header(default=None)):
    raw = tg_id or x_telegram_user_id
    try:
        current = int(str(raw).strip())
    except (ValueError, TypeError):
        raise HTTPException(401, 'Telegram identity required')
    return {'telegram_user_id': current, 'is_admin': is_admin_telegram_id(current), 'maintenance': False}

@app.get('/api/avatar/{telegram_user_id}')
def avatar(telegram_user_id: int):
    # Best-effort proxy of a Telegram profile picture via Bot API; falls back to 404.
    if not BOT_TOKEN:
        raise HTTPException(404, 'Avatar unavailable')
    try:
        photos = telegram_api('getUserProfilePhotos', {'user_id': telegram_user_id, 'limit': 1})
        sizes = photos.get('photos') or []
        if not sizes:
            raise HTTPException(404, 'Avatar unavailable')
        photo = sizes[0][-1]
        file_data = telegram_api('getFile', {'file_id': photo['file_id']})
        path = file_data.get('file_path')
        if not path:
            raise HTTPException(404, 'Avatar unavailable')
        with urllib.request.urlopen(f'https://api.telegram.org/file/bot{BOT_TOKEN}/{path}', timeout=15) as resp:
            content = resp.read()
        media = 'image/jpeg'
        if path.lower().endswith('.png'): media='image/png'
        return StreamingResponse(io.BytesIO(content), media_type=media)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(404, str(exc))


class PromoOpenIn(BaseModel):
    code: str

class AdminPromoIn(BaseModel):
    code: str
    max_uses: int = 0

PROMO_REWARDS = [
    ('ton', '0.1 TON', 0.1, 80.0),
    ('ton', '0.3 TON', 0.3, 10.0),
    ('ton', '0.5 TON', 0.5, 5.0),
    ('ton', '1 TON', 1.0, 2.0),
    ('nft', 'Scared Cat', 1.25, 3.0),
]

def draw_promo_reward():
    roll = random.random() * 100.0
    upto = 0.0
    for kind, name, value, weight in PROMO_REWARDS:
        upto += weight
        if roll < upto:
            if kind == 'nft':
                return {'kind':'nft','name':name,'value':float(value),'image_url':f"https://cdn.changes.tg/gifts/models/{urllib.parse.quote(name)}/png/Original.png"}
            return {'kind':'ton','name':name,'value':float(value),'image_url':''}
    return {'kind':'ton','name':'0.1 TON','value':0.1,'image_url':''}

@app.post('/api/cases/promo/open')
def open_promo_case(payload: PromoOpenIn, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    code = payload.code.strip().upper()
    if not code:
        raise HTTPException(400, 'Введите промокод')
    with db() as con:
        promo = con.execute('SELECT * FROM promo_codes WHERE code=%s FOR UPDATE', (code,)).fetchone()
        if not promo or not promo['active']:
            raise HTTPException(400, 'Промокод не найден или отключён')
        if int(promo['max_uses'] or 0) > 0 and int(promo['used_count'] or 0) >= int(promo['max_uses']):
            raise HTTPException(400, 'Лимит активаций промокода исчерпан')
        used = con.execute('SELECT 1 FROM promo_redemptions WHERE code=%s AND user_id=%s LIMIT 1', (code, u['id'])).fetchone()
        if used:
            raise HTTPException(400, 'Этот промокод уже использован')
        reward = draw_promo_reward()
        now = int(time.time())
        if reward['kind'] == 'ton':
            new_balance = float(u['balance'] or 0) + float(reward['value'])
            con.execute('UPDATE users SET balance=%s WHERE id=%s', (new_balance, u['id']))
        else:
            item_id = uuid.uuid4().hex
            con.execute(
                "INSERT INTO inventory(id,user_id,telegram_gift_id,name,model,backdrop,symbol,image_url,floor,status,created_at) VALUES(%s,%s,%s,%s,'','','',%s,%s,'available',%s)",
                (item_id, u['id'], 'promo-'+item_id, reward['name'], reward['image_url'], float(reward['value']), now)
            )
            new_balance = float(u['balance'] or 0)
        con.execute('INSERT INTO promo_redemptions(code,user_id,reward_kind,reward_name,reward_value,created_at) VALUES(%s,%s,%s,%s,%s,%s)', (code,u['id'],reward['kind'],reward['name'],float(reward['value']),now))
        con.execute('UPDATE promo_codes SET used_count=used_count+1 WHERE code=%s', (code,))
        con.execute("INSERT INTO live_events(user_id,username,name,image_url,value,kind,action_text,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", (u['id'], u['username'] or u['first_name'] or '', reward['name'], reward['image_url'], float(reward['value']), reward['kind'], 'получил по промокоду', now))
    return {'ok':True,'code':code,'reward':reward,'balance':new_balance}

@app.post('/api/admin/promo-code')
def admin_create_promo(payload: AdminPromoIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    code = payload.code.strip().upper()
    if not code or len(code) < 3:
        raise HTTPException(400, 'Код должен содержать минимум 3 символа')
    max_uses = max(0, int(payload.max_uses or 0))
    now = int(time.time())
    with db() as con:
        exists = con.execute('SELECT code FROM promo_codes WHERE code=%s', (code,)).fetchone()
        if exists:
            raise HTTPException(409, 'Такой промокод уже существует')
        con.execute('INSERT INTO promo_codes(code,max_uses,used_count,active,created_at) VALUES(%s,%s,0,TRUE,%s)', (code,max_uses,now))
    return {'ok':True,'code':code,'max_uses':max_uses}

@app.get('/api/admin/promo-codes')
def admin_promo_codes(x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    with db() as con:
        rows = con.execute('SELECT code,max_uses,used_count,active,created_at FROM promo_codes ORDER BY created_at DESC LIMIT 200').fetchall()
    return {'items':[dict(r) for r in rows]}

@app.post('/api/admin/promo-code/toggle')
def admin_toggle_promo(payload: AdminPromoIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    code = payload.code.strip().upper()
    with db() as con:
        row = con.execute('SELECT active FROM promo_codes WHERE code=%s FOR UPDATE', (code,)).fetchone()
        if not row:
            raise HTTPException(404,'Промокод не найден')
        new_active = not bool(row['active'])
        con.execute('UPDATE promo_codes SET active=%s WHERE code=%s', (new_active,code))
    return {'ok':True,'code':code,'active':new_active}

@app.get('/api/admin/overview')
def admin_overview(x_telegram_user_id: str | None = Header(default=None)):
    admin_tg_id=require_admin(x_telegram_user_id)
    with db() as con:
        totals=con.execute('SELECT COUNT(*) AS users, COALESCE(SUM(balance),0) AS balance FROM users').fetchone()
        active=con.execute("SELECT COUNT(*) AS c FROM users WHERE created_at >= %s", (int(time.time())-86400,)).fetchone()['c']
        banned=con.execute('SELECT COUNT(*) AS c FROM users WHERE is_banned=TRUE').fetchone()['c']
        volume=con.execute('SELECT COALESCE(SUM(total_volume),0) AS v FROM user_stats').fetchone()['v']
        top=con.execute('SELECT u.username,u.first_name,u.avatar_url,COALESCE(s.total_volume,0) AS volume FROM users u LEFT JOIN user_stats s ON s.user_id=u.id ORDER BY COALESCE(s.total_volume,0) DESC LIMIT 20').fetchall()
    return {'admin_tg_id':admin_tg_id,'users':int(totals['users'] or 0),'balance':float(totals['balance'] or 0),'active_24h':int(active),'banned':int(banned),'volume':float(volume or 0),'top':[dict(x) for x in top]}

class AdminUserIn(BaseModel):
    username: str

class AdminBalanceIn(AdminUserIn):
    amount: float

@app.post('/api/admin/balance')
def admin_balance(payload: AdminBalanceIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    uname=payload.username.strip().lstrip('@').lower()
    amount=float(payload.amount)
    with db() as con:
        u=con.execute('SELECT * FROM users WHERE LOWER(username)=LOWER(%s) LIMIT 1 FOR UPDATE',(uname,)).fetchone()
        if not u: raise HTTPException(404,'Пользователь не найден')
        newbal=float(u['balance'] or 0)+amount
        if newbal < 0: raise HTTPException(400,'Баланс не может быть отрицательным')
        con.execute('UPDATE users SET balance=%s WHERE id=%s',(newbal,u['id']))
        con.execute("INSERT INTO activity_log(user_id,type,amount,name,created_at) VALUES(%s,'admin_balance',%s,'Admin balance change',%s)",(u['id'],amount,int(time.time())))
    return {'ok':True,'username':u['username'],'balance':newbal}

class AdminGiftIn(AdminUserIn):
    name: str
    image_url: str = ''
    floor: float = 0
    backdrop: str = ''

@app.post('/api/admin/gift')
def admin_gift(payload: AdminGiftIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    uname=payload.username.strip().lstrip('@').lower()
    img=payload.image_url.strip() or f"https://cdn.changes.tg/gifts/models/{urllib.parse.quote(payload.name)}/png/Original.png"
    with db() as con:
        u=con.execute('SELECT * FROM users WHERE LOWER(username)=LOWER(%s) LIMIT 1 FOR UPDATE',(uname,)).fetchone()
        if not u: raise HTTPException(404,'Пользователь не найден')
        item_id=uuid.uuid4().hex
        con.execute("INSERT INTO inventory(id,user_id,telegram_gift_id,name,model,backdrop,symbol,image_url,floor,status,created_at) VALUES(%s,%s,%s,%s,'','','',%s,%s,'available',%s)", (item_id,u['id'],'admin-'+item_id,payload.name[:120],img,float(payload.floor or 0),int(time.time())))
        con.execute("INSERT INTO live_events(user_id,username,name,image_url,value,kind,action_text,created_at) VALUES(%s,%s,%s,%s,%s,'nft','получил NFT от администрации',%s)",(u['id'],u['username'] or u['first_name'] or '',payload.name[:120],img,float(payload.floor or 0),int(time.time())))
    return {'ok':True,'inventory_id':item_id}

class AdminBroadcastIn(BaseModel):
    text: str

@app.post('/api/admin/broadcast')
def admin_broadcast(payload: AdminBroadcastIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    if not payload.text.strip(): raise HTTPException(400,'Пустое сообщение')
    if not BOT_TOKEN: raise HTTPException(500,'BOT_TOKEN is not configured')
    with db() as con:
        rows=con.execute('SELECT telegram_user_id FROM users WHERE is_banned=FALSE').fetchall()
    ok=0; failed=0
    for r in rows:
        try:
            telegram_api('sendMessage', {'chat_id':int(r['telegram_user_id']),'text':payload.text[:4096]})
            ok+=1
        except Exception:
            failed+=1
    return {'ok':True,'sent':ok,'failed':failed,'total':len(rows)}


@app.post('/api/admin/ban')
def admin_ban(payload: AdminUserIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    uname=payload.username.strip().lstrip('@').lower()
    with db() as con:
        u=con.execute('SELECT * FROM users WHERE LOWER(username)=LOWER(%s) LIMIT 1 FOR UPDATE',(uname,)).fetchone()
        if not u: raise HTTPException(404,'Пользователь не найден')
        con.execute("UPDATE users SET is_banned=TRUE,ban_reason='Заблокирован администрацией' WHERE id=%s",(u['id'],))
    return {'ok':True,'username':u['username'],'banned':True}

@app.post('/api/admin/unban')
def admin_unban(payload: AdminUserIn, x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    uname=payload.username.strip().lstrip('@').lower()
    with db() as con:
        u=con.execute('SELECT * FROM users WHERE LOWER(username)=LOWER(%s) LIMIT 1 FOR UPDATE',(uname,)).fetchone()
        if not u: raise HTTPException(404,'Пользователь не найден')
        con.execute("UPDATE users SET is_banned=FALSE,ban_reason='' WHERE id=%s",(u['id'],))
    return {'ok':True,'username':u['username'],'banned':False}

@app.get('/api/admin/users')
def admin_users(x_telegram_user_id: str | None = Header(default=None)):
    require_admin(x_telegram_user_id)
    with db() as con:
        rows=con.execute("SELECT u.id,u.telegram_user_id,u.username,u.first_name,u.last_name,u.avatar_url,u.balance,u.referral_count,u.referral_earnings,u.is_banned,COALESCE(s.total_volume,0) AS volume,COALESCE(s.arena_wins,0) AS wins FROM users u LEFT JOIN user_stats s ON s.user_id=u.id ORDER BY u.created_at DESC LIMIT 200").fetchall()
    return {'items':[dict(r) for r in rows]}

def get_mrkt_token(force=False):
    # Preferred path: ask the already-authenticated Telegram user-session worker to
    # mint a fresh MRKT token. This removes the need to rotate MRKT_AUTH_TOKEN by hand.
    if MRKT_WORKER_URL:
        try:
            url = MRKT_WORKER_URL + '/internal/mrkt/token'
            if force:
                url += '?force=1'
            req = urllib.request.Request(
                url,
                headers={'Accept': 'application/json', 'X-Worker-Secret': os.getenv('WORKER_SECRET', '')},
                method='GET',
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode())
            token = str(data.get('token') or '').strip()
            if token:
                return token
        except Exception:
            pass
    # Backward-compatible emergency fallback for deployments that still set a token.
    return MRKT_AUTH_TOKEN_FALLBACK


def mrkt_gifts_request(token, payload):
    req = urllib.request.Request(
        'https://api.tgmrkt.io/api/v1/gifts/saling',
        data=json.dumps(payload).encode(),
        headers={
            'Accept':'application/json',
            'Content-Type':'application/json',
            'Authorization':token,
            'Referer':'https://cdn.tgmrkt.io/'
        },
        method='POST'
    )
    return urllib.request.urlopen(req, timeout=12)


@app.get('/api/rare-gift-floors')
def rare_gift_floors(x_telegram_user_id: str | None = Header(default=None), backdrop: str = 'all', limit: int = 300):
    # MRKT auth is minted server-to-server from the Telegram user-session worker.
    token = get_mrkt_token(force=False)
    wanted = [b for b in (['Black','Onyx Black'] if backdrop.lower()=='all' else [backdrop])]
    fallback = [
      {'name':'Jelly Bunny','number':'#1','backdrop':'Black','floor':23.46,'img':'https://cdn.changes.tg/gifts/models/Jelly%20Bunny/png/Original.png','kind':'black'},
      {'name':'Witch Hat','number':'#47969','backdrop':'Onyx Black','floor':33.04,'img':'https://cdn.changes.tg/gifts/models/Witch%20Hat/png/Original.png','kind':'onyx'},
      {'name':'Joyful Bundle','number':'#52841','backdrop':'Onyx Black','floor':20.00,'img':'https://cdn.changes.tg/gifts/models/Joyful%20Bundle/png/Original.png','kind':'onyx'},
      {'name':'Plush Pepe','number':'#1','backdrop':'Onyx Black','floor':5916.00,'img':'https://cdn.changes.tg/gifts/models/Plush%20Pepe/png/Original.png','kind':'onyx'}
    ]
    if not token:
        return {'items':fallback, 'source':'fallback', 'count':len(fallback)}
    items=[]
    for bg in wanted:
        cursor=''
        for _ in range(max(1,min(50,(limit//20)+2))):
            payload={"collectionNames":[],"modelNames":[],"backdropNames":[bg],"symbolNames":[],"ordering":"Price","lowToHigh":True,"maxPrice":None,"minPrice":None,"mintable":None,"number":None,"count":20,"cursor":cursor,"query":None,"promotedFirst":False}
            try:
                with mrkt_gifts_request(token, payload) as resp:
                    data=json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403) and MRKT_WORKER_URL:
                    token = get_mrkt_token(force=True)
                    if not token:
                        break
                    try:
                        with mrkt_gifts_request(token, payload) as resp:
                            data=json.loads(resp.read().decode())
                    except Exception:
                        break
                else:
                    break
            except Exception:
                break
            gifts=data.get('gifts') or []
            if not gifts: break
            for g in gifts:
                price=float(g.get('price') or g.get('floor') or g.get('amount') or 0)
                if price<=0: continue
                name=g.get('name') or g.get('collectionName') or g.get('collection') or 'Gift'
                backdrop_name=g.get('backdropName') or g.get('backdrop') or bg
                image=g.get('image_url') or g.get('imageUrl') or g.get('img') or f"https://cdn.changes.tg/gifts/models/{name.replace(' ','%20')}/png/Original.png"
                items.append({'name':name,'number':g.get('number') or g.get('giftNumber') or '','backdrop':backdrop_name,'floor':price,'img':image,'kind':'onyx' if backdrop_name.lower()=='onyx black' else 'black'})
            cursor=data.get('cursor') or ''
            if not cursor or len(items)>=limit: break
    # Keep all fetched listings; dedupe by gift identity.
    seen=set(); out=[]
    for x in items:
        k=(x['name'],x['number'],x['backdrop'])
        if k in seen: continue
        seen.add(k); out.append(x)
        if len(out)>=limit: break
    out.sort(key=lambda x: x['floor'])
    return {'items':out, 'source':'mrkt', 'count':len(out)}

@app.get('/api/withdrawals')
def withdrawals(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        rows = con.execute('SELECT * FROM withdrawals WHERE user_id=%s ORDER BY created_at DESC LIMIT 50', (u['id'],)).fetchall()
    return {'items': rows}

# ===== v9 wallet + synchronized Crash =====

def ensure_v9_tables(con):
    con.execute("""CREATE TABLE IF NOT EXISTS crash_rounds (
        id UUID PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'waiting',
        crash_point DOUBLE PRECISION NOT NULL,
        created_at BIGINT NOT NULL,
        started_at BIGINT,
        crashed_at BIGINT
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_crash_rounds_status_created ON crash_rounds(status,created_at DESC)")
    con.execute("""CREATE TABLE IF NOT EXISTS crash_bets (
        id BIGSERIAL PRIMARY KEY,
        round_id UUID NOT NULL REFERENCES crash_rounds(id) ON DELETE CASCADE,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        stake DOUBLE PRECISION NOT NULL,
        cashout_multiplier DOUBLE PRECISION,
        payout DOUBLE PRECISION,
        created_at BIGINT NOT NULL
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_crash_bets_round_created ON crash_bets(round_id,created_at DESC)")

class DepositIntentIn(BaseModel):
    wallet_address: str
    amount: float

@app.post('/api/deposit/intent')
def create_deposit_intent(payload: DepositIntentIn, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    wallet = str(payload.wallet_address or '').strip()
    amount = round(float(payload.amount or 0), 6)
    if not wallet or len(wallet) < 20:
        raise HTTPException(400, 'Invalid TON wallet')
    if amount < 0.01:
        raise HTTPException(400, 'Минимум 0.01 TON')
    if not TON_DEPOSIT_WALLET:
        raise HTTPException(503, 'Депозитный кошелёк не настроен')
    amount_nano = int(round(amount * 1_000_000_000))
    now = int(time.time())
    with db() as con:
        # One pending intent per wallet prevents ambiguous same-amount transfers.
        con.execute("UPDATE ton_deposits SET status='expired' WHERE wallet_address=%s AND status='pending' AND created_at < %s", (wallet, now-15*60))
        pending = con.execute("SELECT id FROM ton_deposits WHERE wallet_address=%s AND status='pending' LIMIT 1", (wallet,)).fetchone()
        if pending:
            raise HTTPException(409, 'У этого кошелька уже есть ожидающее пополнение')
        dep_id = str(uuid.uuid4())
        con.execute("INSERT INTO ton_deposits(id,user_id,wallet_address,amount_nano,status,created_at) VALUES(%s,%s,%s,%s,'pending',%s)", (dep_id,u['id'],wallet,amount_nano,now))
    return {'ok': True, 'deposit_id': dep_id, 'amount': amount, 'status': 'pending'}

@app.get('/api/deposit/status/{deposit_id}')
def deposit_status(deposit_id: str, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        row = con.execute("SELECT id,amount_nano,status,tx_hash,confirmed_at FROM ton_deposits WHERE id=%s AND user_id=%s", (deposit_id,u['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Deposit not found')
        bal = con.execute('SELECT balance FROM users WHERE id=%s',(u['id'],)).fetchone()['balance']
    return {'ok': True, 'status': row['status'], 'tx_hash': row['tx_hash'], 'balance': float(bal or 0)}

def _ton_get_transactions(address: str):
    q = urllib.parse.urlencode({'address': address, 'limit': 30})
    req = urllib.request.Request(f"{TON_API_BASE}/getTransactions?{q}", headers={'X-API-Key':TON_API_KEY} if TON_API_KEY else {})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data=json.loads(resp.read().decode())
    if not data.get('ok'):
        raise RuntimeError(data.get('error') or 'TON API error')
    return data.get('result') or []

def _norm_addr(v):
    if isinstance(v, dict):
        v=v.get('account_address') or v.get('account') or ''
    return str(v or '').strip()

def _scan_ton_deposits_once():
    if not TON_DEPOSIT_WALLET:
        return 0
    with db() as con:
        pending=con.execute("SELECT * FROM ton_deposits WHERE status='pending' AND created_at >= %s ORDER BY created_at ASC LIMIT 50", (int(time.time())-20*60,)).fetchall()
    if not pending:
        return 0
    try:
        txs=_ton_get_transactions(TON_DEPOSIT_WALLET)
    except Exception:
        return 0
    matched=0
    for tx in txs:
        inmsg=tx.get('in_msg') or {}
        source=_norm_addr(inmsg.get('source'))
        dest=_norm_addr(inmsg.get('destination'))
        value=int(str(inmsg.get('value') or '0'))
        if not source or value<=0 or (dest and dest not in (TON_DEPOSIT_WALLET, _norm_addr(TON_DEPOSIT_WALLET))):
            continue
        txid=((tx.get('transaction_id') or {}).get('hash') or inmsg.get('hash') or '')
        if not txid:
            continue
        # Do not credit a transaction twice.
        with db() as con:
            already=con.execute('SELECT 1 FROM ton_deposits WHERE tx_hash=%s LIMIT 1',(txid,)).fetchone()
        if already:
            continue
        candidates=[d for d in pending if d['status']=='pending' and d['wallet_address'].strip()==source and int(d['amount_nano'])==value]
        if not candidates:
            continue
        dep=candidates[0]
        with db() as con:
            row=con.execute("SELECT * FROM ton_deposits WHERE id=%s FOR UPDATE",(dep['id'],)).fetchone()
            if not row or row['status']!='pending':
                continue
            amount=value/1_000_000_000
            con.execute('UPDATE users SET balance=balance+%s WHERE id=%s',(amount,row['user_id']))
            con.execute("UPDATE ton_deposits SET status='confirmed',tx_hash=%s,confirmed_at=%s WHERE id=%s",(txid,int(time.time()),row['id']))
            con.execute("INSERT INTO activity_log(user_id,type,amount,name,created_at) VALUES(%s,'deposit',%s,'TON Connect',%s)",(row['user_id'],amount,int(time.time())))
        matched+=1
        pending=[d for d in pending if d['id']!=dep['id']]
    return matched

async def ton_deposit_loop():
    while True:
        try:
            await asyncio.to_thread(_scan_ton_deposits_once)
        except Exception:
            pass
        await asyncio.sleep(8)

@app.on_event('startup')
async def _start_ton_deposit_loop():
    asyncio.create_task(ton_deposit_loop())

class V9WalletAmount(BaseModel):
    amount: float
    reason: str = ''

@app.get('/api/wallet')
def v9_wallet(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    return {'balance': float(u['balance'] or 0)}

@app.post('/api/wallet/charge')
def v9_wallet_charge(payload: V9WalletAmount, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    amount = round(float(payload.amount), 6)
    if amount <= 0:
        raise HTTPException(400, 'Invalid amount')
    with db() as con:
        row = con.execute('SELECT * FROM users WHERE id=%s FOR UPDATE', (u['id'],)).fetchone()
        if float(row['balance'] or 0) + 1e-9 < amount:
            raise HTTPException(400, 'Недостаточно TON')
        now = int(time.time())
        con.execute('UPDATE users SET balance=balance-%s WHERE id=%s', (amount, u['id']))
        con.execute("INSERT INTO activity_log(user_id,type,amount,name,created_at) VALUES(%s,'wallet_charge',%s,%s,%s)", (u['id'], amount, payload.reason[:120] or 'Списание', now))
        con.execute('INSERT INTO user_stats(user_id,total_volume,updated_at) VALUES(%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET total_volume=user_stats.total_volume+EXCLUDED.total_volume,updated_at=EXCLUDED.updated_at', (u['id'], amount, now))
        balance = float(row['balance'] or 0) - amount
    return {'ok': True, 'balance': balance}

@app.post('/api/wallet/credit')
def v9_wallet_credit(payload: V9WalletAmount, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    amount = round(float(payload.amount), 6)
    if amount <= 0:
        raise HTTPException(400, 'Invalid amount')
    with db() as con:
        con.execute('UPDATE users SET balance=balance+%s WHERE id=%s', (amount, u['id']))
        balance = float(con.execute('SELECT balance FROM users WHERE id=%s', (u['id'],)).fetchone()['balance'])
    return {'ok': True, 'balance': balance}

def v9_crash_multiplier(elapsed: float) -> float:
    return max(1.0, math.exp(0.17 * max(0.0, elapsed)))

def v9_new_crash_point() -> float:
    return round(max(1.10, min(25.0, math.exp(random.uniform(math.log(1.10), math.log(7.5))))), 2)

def v9_ensure_round(con):
    ensure_v9_tables(con)
    now = int(time.time())
    r = con.execute("SELECT * FROM crash_rounds WHERE status IN ('waiting','flying') ORDER BY created_at DESC LIMIT 1 FOR UPDATE").fetchone()
    if r:
        if r['status'] == 'waiting' and now >= int(r['created_at']) + 5:
            con.execute("UPDATE crash_rounds SET status='flying',started_at=%s WHERE id=%s", (now, r['id']))
            r = con.execute('SELECT * FROM crash_rounds WHERE id=%s', (r['id'],)).fetchone()
        if r['status'] == 'flying':
            mult = v9_crash_multiplier(now - int(r['started_at'] or now))
            if mult >= float(r['crash_point']):
                con.execute("UPDATE crash_rounds SET status='crashed',crashed_at=%s WHERE id=%s", (now, r['id']))
                r = con.execute('SELECT * FROM crash_rounds WHERE id=%s', (r['id'],)).fetchone()
        return r
    rid = uuid.uuid4()
    con.execute("INSERT INTO crash_rounds(id,status,crash_point,created_at) VALUES(%s,'waiting',%s,%s)", (rid, v9_new_crash_point(), now))
    return con.execute('SELECT * FROM crash_rounds WHERE id=%s', (rid,)).fetchone()

def v9_crash_payload(con, r, uid):
    players = con.execute("""SELECT b.id,b.user_id,b.stake,b.cashout_multiplier,b.payout,b.created_at,u.username,u.first_name,u.last_name,u.avatar_url
                            FROM crash_bets b JOIN users u ON u.id=b.user_id WHERE b.round_id=%s ORDER BY b.created_at ASC""", (r['id'],)).fetchall()
    now = int(time.time())
    waiting = max(0, int(r['created_at']) + 5 - now) if r['status'] == 'waiting' else 0
    mult = 1.0
    if r['status'] == 'flying' and r['started_at']:
        mult = min(float(r['crash_point']), v9_crash_multiplier(now - int(r['started_at'])))
    return {'round': dict(r), 'multiplier': round(mult, 2), 'waiting_seconds': waiting, 'bets': [dict(x) for x in players], 'you_user_id': uid}

@app.get('/api/crash/current')
def v9_crash_current(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        r = v9_ensure_round(con)
        return v9_crash_payload(con, r, u['id'])

class V9CrashBet(BaseModel):
    amount: float

@app.post('/api/crash/bet')
def v9_crash_bet(payload: V9CrashBet, x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    amount = round(float(payload.amount), 6)
    if amount < 0.1:
        raise HTTPException(400, 'Минимальная ставка — 0.1 TON')
    with db() as con:
        r = v9_ensure_round(con)
        if r['status'] != 'waiting':
            raise HTTPException(409, 'Ставка доступна до старта раунда')
        if con.execute('SELECT 1 FROM crash_bets WHERE round_id=%s AND user_id=%s', (r['id'], u['id'])).fetchone():
            raise HTTPException(409, 'В этом раунде ставка уже сделана')
        row = con.execute('SELECT * FROM users WHERE id=%s FOR UPDATE', (u['id'],)).fetchone()
        if float(row['balance'] or 0) + 1e-9 < amount:
            raise HTTPException(400, 'Недостаточно TON')
        now = int(time.time())
        con.execute('UPDATE users SET balance=balance-%s WHERE id=%s', (amount, u['id']))
        con.execute('INSERT INTO crash_bets(round_id,user_id,stake,created_at) VALUES(%s,%s,%s,%s)', (r['id'], u['id'], amount, now))
        con.execute("INSERT INTO activity_log(user_id,type,amount,name,created_at) VALUES(%s,'crash_bet',%s,'Crash',%s)", (u['id'], amount, now))
        con.execute('INSERT INTO user_stats(user_id,total_volume,updated_at) VALUES(%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET total_volume=user_stats.total_volume+EXCLUDED.total_volume,updated_at=EXCLUDED.updated_at', (u['id'], amount, now))
        con.execute("INSERT INTO live_events(user_id,username,name,image_url,value,kind,action_text,created_at) VALUES(%s,%s,'Crash','',%s,'ton',%s,%s)", (u['id'], u['username'] or u['first_name'] or '', amount, f'поставил {amount:.2f} TON в Crash', now))
        balance = float(row['balance'] or 0) - amount
        return {'ok': True, 'balance': balance, **v9_crash_payload(con, r, u['id'])}

@app.post('/api/crash/cashout')
def v9_crash_cashout(x_telegram_user_id: str | None = Header(default=None)):
    u = current_user(x_telegram_user_id)
    with db() as con:
        r = v9_ensure_round(con)
        bet = con.execute('SELECT * FROM crash_bets WHERE round_id=%s AND user_id=%s AND cashout_multiplier IS NULL ORDER BY id DESC LIMIT 1 FOR UPDATE', (r['id'], u['id'])).fetchone()
        if not bet:
            raise HTTPException(404, 'Активной ставки нет')
        if r['status'] != 'flying':
            raise HTTPException(409, 'Раунд уже завершён')
        now = int(time.time())
        mult = round(min(float(r['crash_point']), v9_crash_multiplier(now - int(r['started_at'] or now))), 2)
        if mult >= float(r['crash_point']):
            con.execute("UPDATE crash_rounds SET status='crashed',crashed_at=%s WHERE id=%s", (now, r['id']))
            raise HTTPException(409, 'Слишком поздно — краш')
        payout = round(float(bet['stake']) * mult, 6)
        con.execute('UPDATE crash_bets SET cashout_multiplier=%s,payout=%s WHERE id=%s', (mult, payout, bet['id']))
        con.execute('UPDATE users SET balance=balance+%s WHERE id=%s', (payout, u['id']))
        con.execute("INSERT INTO live_events(user_id,username,name,image_url,value,kind,action_text,created_at) VALUES(%s,%s,'Crash','',%s,'ton',%s,%s)", (u['id'], u['username'] or u['first_name'] or '', payout, f'забрал {payout:.2f} TON в Crash на x{mult:.2f}', now))
        con.execute("INSERT INTO activity_log(user_id,type,amount,name,value,kind,action_text,created_at) VALUES(%s,'crash_win',0,'Crash',%s,'ton',%s,%s)", (u['id'], payout, f'забрал {payout:.2f} TON в Crash на x{mult:.2f}', now))
        balance = float(con.execute('SELECT balance FROM users WHERE id=%s', (u['id'],)).fetchone()['balance'])
        return {'ok': True, 'balance': balance, 'payout': payout, 'multiplier': mult, **v9_crash_payload(con, r, u['id'])}

@app.get('/api/crash/feed')
def v9_crash_feed(x_telegram_user_id: str | None = Header(default=None)):
    current_user(x_telegram_user_id)
    with db() as con:
        rows = con.execute("SELECT * FROM live_events WHERE action_text ILIKE '%Crash%' ORDER BY created_at DESC LIMIT 50").fetchall()
    return {'items': [dict(x) for x in rows]}
