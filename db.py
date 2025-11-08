# db.py
import sqlite3, json
from datetime import datetime, timedelta, timezone
import hashlib
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join("data", "words.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def connect():
    return sqlite3.connect(DB_PATH)

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def init_db():
    with connect() as cx:
        cur = cx.cursor()
        cur.execute("PRAGMA table_info(words)")
        cols = [r[1] for r in cur.fetchall()]
        if "block_until_ru_de" not in cols:
            cur.execute("ALTER TABLE words ADD COLUMN block_until_ru_de TEXT DEFAULT NULL")
            cx.commit()
            print("[DB] Added column block_until_ru_de]")

        # заполняем новым полем для старых записей текущим временем (чтобы блок считался истёкшим)
        cur.execute(
            "UPDATE words SET block_until_ru_de=? WHERE block_until_ru_de IS NULL",
            (datetime.now(timezone.utc).isoformat(),)
        )
        cx.commit()
        print("[DB] Filled missing block_until_ru_de with current time")

        # таблица слов
        cx.execute("""
        CREATE TABLE IF NOT EXISTS words(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          de TEXT NOT NULL,
          ru TEXT NOT NULL,
          next_de_ru TEXT,
          next_ru_de TEXT,
          interval_de_ru INTEGER DEFAULT 0,
          interval_ru_de INTEGER DEFAULT 0,
          correct_de_ru INTEGER DEFAULT 0,
          correct_ru_de INTEGER DEFAULT 0,
          created_at TEXT,
          history TEXT DEFAULT '[]'
        );
        """)
        cx.execute("CREATE INDEX IF NOT EXISTS idx_words_user ON words(user_id);")

        # таблица пользователей
        cx.execute("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          created_at TEXT
        );
        """)

def create_user(email: str, password: str):
    with connect() as cx:
        h = hash_password(password)
        now = datetime.now(timezone.utc).isoformat()
        try:
            cx.execute("INSERT INTO users (email, password_hash, created_at) VALUES (?,?,?)", (email, h, now))
            return True
        except sqlite3.IntegrityError:
            return False

def get_user_by_email(email: str):
    with connect() as cx:
        cur = cx.execute("SELECT id, email, password_hash, created_at FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "password_hash": row[2], "created_at": row[3]}

def verify_user(email: str, password: str):
    u = get_user_by_email(email)
    if not u:
        return False
    return u["password_hash"] == hash_password(password)

def row_to_dict(r):
    keys = ["id","user_id","de","ru","next_de_ru","next_ru_de",
            "interval_de_ru","interval_ru_de","correct_de_ru","correct_ru_de",
            "created_at","history", "block_until_ru_de"]
    d = dict(zip(keys, r))
    d["history"] = json.loads(d["history"] or "[]")
    return d

def get_words(user_id:str):
    with connect() as cx:
        cur = cx.execute("""SELECT id,user_id,de,ru,next_de_ru,next_ru_de,
                                   interval_de_ru,interval_ru_de,correct_de_ru,correct_ru_de,
                                   created_at,history,block_until_ru_de
                            FROM words WHERE user_id=? ORDER BY id""", (user_id,))
        return [row_to_dict(r) for r in cur.fetchall()]

def add_word(user_id:str, de:str, ru:str):
    t = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    created = datetime.now(timezone.utc).isoformat()
    with connect() as cx:
        cur = cx.execute("""INSERT INTO words
            (user_id,de,ru,next_de_ru,next_ru_de,interval_de_ru,interval_ru_de,
             correct_de_ru,correct_ru_de,created_at,history)
            VALUES (?,?,?,?,?,0,0,0,0,?,?)""",
            (user_id, de, ru, t, t, created, "[]"))
        wid = cur.lastrowid
        block_until = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        cx.execute("UPDATE words SET block_until_ru_de=? WHERE id=? AND user_id=?", (block_until, wid, user_id))
        r = cx.execute("""SELECT id,user_id,de,ru,next_de_ru,next_ru_de,
                                 interval_de_ru,interval_ru_de,correct_de_ru,correct_ru_de,
                                 created_at,history
                          FROM words WHERE id=? AND user_id=?""", (wid, user_id)).fetchone()
        return row_to_dict(r)

def update_result(user_id:str, word_id:int, correct:bool, reverse:bool, intervals, fast:bool):
    with connect() as cx:
        r = cx.execute("""SELECT id,user_id,de,ru,next_de_ru,next_ru_de,
                                 interval_de_ru,interval_ru_de,correct_de_ru,correct_ru_de,
                                 created_at,history
                          FROM words WHERE id=? AND user_id=?""", (word_id, user_id)).fetchone()
        if not r: return None
        w = row_to_dict(r)

        # history
        w["history"].append({
            "date": datetime.now(timezone.utc).date().isoformat(),
            "correct": bool(correct),
            "reverse": bool(reverse)
        })

        key_int = "interval_ru_de" if reverse else "interval_de_ru"
        key_next = "next_ru_de" if reverse else "next_de_ru"
        key_corr = "correct_ru_de" if reverse else "correct_de_ru"

        if correct:
            w[key_int] = min((w[key_int] or 0) + 1, len(intervals) - 1)
            w[key_corr] = (w[key_corr] or 0) + 1
        else:
            w[key_int] = 0

        hours = intervals[w[key_int]]
        if fast and hours:
            hours = hours / 30.0
        next_time = (datetime.now(timezone.utc) + timedelta(seconds=2, hours=hours)).isoformat()
        w[key_next] = next_time

        # блокировка DE→RU на 6 часов после успешного RU→DE
        if correct and not reverse:
            block_until = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
            w["block_until_ru_de"] = block_until
            cx.execute("UPDATE words SET block_until_ru_de=? WHERE id=? AND user_id=?", (block_until, word_id, user_id))

        cx.execute("""UPDATE words
                      SET next_de_ru=?, next_ru_de=?,
                          interval_de_ru=?, interval_ru_de=?,
                          correct_de_ru=?, correct_ru_de=?,
                          history=?
                      WHERE id=? AND user_id=?""",
                   (w["next_de_ru"], w["next_ru_de"],
                    w["interval_de_ru"], w["interval_ru_de"],
                    w["correct_de_ru"], w["correct_ru_de"],
                    json.dumps(w["history"], ensure_ascii=False),
                    word_id, user_id))
        return w

def reset_user(user_id:str):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as cx:
        cx.execute("""UPDATE words
                      SET interval_de_ru=0, interval_ru_de=0,
                          correct_de_ru=0, correct_ru_de=0,
                          next_de_ru=?, next_ru_de=?,
                          block_until_ru_de=NULL
                      WHERE user_id=?""", (now, now, user_id))
        block_until = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        cx.execute("UPDATE words SET block_until_ru_de=? WHERE user_id=?", (block_until, user_id))