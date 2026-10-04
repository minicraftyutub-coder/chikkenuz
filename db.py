import os, sqlite3
from contextlib import contextmanager
from dotenv import load_dotenv
load_dotenv()
DB_PATH=os.getenv("DATABASE_PATH","chicken_money.db")
@contextmanager
def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row
    try:
        yield c; c.commit()
    except: c.rollback(); raise
    finally: c.close()
def init_db():
    with db() as c:
        c.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_id INTEGER UNIQUE NOT NULL,username TEXT,first_name TEXT,balance REAL DEFAULT 0,eggs REAL DEFAULT 0,referral_code TEXT UNIQUE,referred_by INTEGER,banned INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chicken_types(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,price REAL,lifetime_days INTEGER,eggs_per_hour REAL,feed_per_hour REAL,multiplier REAL DEFAULT 1,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS chickens(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,chicken_type_id INTEGER,purchased_at TEXT DEFAULT CURRENT_TIMESTAMP,last_production_at TEXT DEFAULT CURRENT_TIMESTAMP,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount_uzs REAL,asset TEXT,network TEXT,wallet TEXT,tx_hash TEXT,screenshot_path TEXT,status TEXT DEFAULT 'pending',admin_note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount_uzs REAL,commission_pct REAL,commission_uzs REAL,payout_uzs REAL,asset TEXT,network TEXT,wallet TEXT,tx_hash TEXT,status TEXT DEFAULT 'pending',admin_note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,type TEXT,amount REAL,note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS admin_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,admin_telegram_id INTEGER,action TEXT,target TEXT,details TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
""")
        defaults={"egg_price_uzs":"500","min_deposit_uzs":"120000","max_deposit_uzs":"10000000","min_withdraw_uzs":"120000","max_withdraw_uzs":"5000000","withdraw_commission_pct":"5","deposit_wallet":"","deposit_asset":"USDT","deposit_network":"TON","daily_bonus_uzs":"5000","referral_pct":"5","egg_storage_limit":"500"}
        for k,v in defaults.items(): c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
        if c.execute("SELECT COUNT(*) n FROM chicken_types").fetchone()["n"]==0:
            c.execute("INSERT INTO chicken_types(name,price,lifetime_days,eggs_per_hour,feed_per_hour,multiplier) VALUES(?,?,?,?,?,?)",("Basic Chicken",50000,30,10,2,1))
            c.execute("INSERT INTO chicken_types(name,price,lifetime_days,eggs_per_hour,feed_per_hour,multiplier) VALUES(?,?,?,?,?,?)",("Golden Chicken",500000,60,60,2,1))
def get_settings():
    with db() as c:return {r["key"]:r["value"] for r in c.execute("SELECT key,value FROM settings")}
def set_setting(k,v):
    with db() as c:c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
