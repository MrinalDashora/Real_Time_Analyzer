import sqlite3
import datetime

DB_NAME = "cognisense.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        role TEXT DEFAULT 'free',
        credits INTEGER DEFAULT 1000,
        otp TEXT,
        otp_expiry TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS cache (
        query TEXT PRIMARY KEY,
        result TEXT,
        timestamp TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def get_user(email):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user

def update_otp(email, otp):
    expiry = datetime.datetime.now() + datetime.timedelta(minutes=5)
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user:
        conn.execute("UPDATE users SET otp = ?, otp_expiry = ? WHERE email = ?", (otp, expiry, email))
    else:
        conn.execute("INSERT INTO users (email, role, credits, otp, otp_expiry) VALUES (?, 'free', 1000, ?, ?)", (email, otp, expiry))
    conn.commit()
    conn.close()

def deduct_credits(email, amount):
    conn = get_db()
    conn.execute("UPDATE users SET credits = credits - ? WHERE email = ?", (amount, email))
    conn.commit()
    conn.close()

def save_cache(query, result):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", 
                   (query, result, datetime.datetime.now()))
    conn.commit()
    conn.close()