import os
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict

DB_PATH = Path("./sessions/cookies.db")

class CookieDatabase:
    def __init__(self):
        self.use_postgres = bool(os.environ.get("DATABASE_URL"))
        self._init_db()

    def _get_connection(self):
        if self.use_postgres:
            import psycopg2
            return psycopg2.connect(os.environ.get("DATABASE_URL"))
        else:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(str(DB_PATH))

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        if self.use_postgres:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_cookies (
                    user_id VARCHAR(100),
                    platform VARCHAR(50),
                    cookies TEXT,
                    updated_at DOUBLE PRECISION,
                    PRIMARY KEY (user_id, platform)
                );
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_cookies (
                    user_id TEXT,
                    platform TEXT,
                    cookies TEXT,
                    updated_at REAL,
                    PRIMARY KEY (user_id, platform)
                );
            """)
        conn.commit()
        conn.close()

    def save_cookies(self, user_id: str, platform: str, cookies: list) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cookies_str = json.dumps(cookies)
        import time
        now = time.time()
        
        try:
            if self.use_postgres:
                cursor.execute("""
                    INSERT INTO user_cookies (user_id, platform, cookies, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, platform) 
                    DO UPDATE SET cookies = EXCLUDED.cookies, updated_at = EXCLUDED.updated_at;
                """, (user_id, platform, cookies_str, now))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO user_cookies (user_id, platform, cookies, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, platform, cookies_str, now))
            conn.commit()
            return True
        except Exception as e:
            print("Database save error:", e)
            return False
        finally:
            conn.close()

    def get_cookies(self, user_id: str, platform: str) -> Optional[list]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            if self.use_postgres:
                cursor.execute("SELECT cookies FROM user_cookies WHERE user_id = %s AND platform = %s", (user_id, platform))
            else:
                cursor.execute("SELECT cookies FROM user_cookies WHERE user_id = ? AND platform = ?", (user_id, platform))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None
        except Exception:
            return None
        finally:
            conn.close()

# Global database manager instance
db = CookieDatabase()
