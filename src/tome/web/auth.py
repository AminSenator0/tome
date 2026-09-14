import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass
class User:
    id: int
    username: str
    is_admin: bool
    created_at: float


class AuthManager:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_dir = Path(".tome")
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "web_users.db"
        self.db_path = db_path
        self._init_db()
        self._failed_attempts: dict[str, list[float]] = {}
        self._active_sessions: dict[str, dict[str, Any]] = {}

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
                """)
            conn.commit()

        self._seed_default_users()

    def _hash_password(self, password: str, salt_hex: str) -> str:
        salt = bytes.fromhex(salt_hex)
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()

    def _seed_default_users(self) -> None:
        defaults = [
            ("aren", "0009"),
            ("mobina", "1383"),
            ("khorshid", "1382"),
        ]
        with self._get_connection() as conn:
            for username, password in defaults:
                cur = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
                if not cur.fetchone():
                    salt_hex = secrets.token_hex(16)
                    p_hash = self._hash_password(password, salt_hex)
                    conn.execute(
                        "INSERT INTO users (username, password_hash, salt, is_admin, created_at) VALUES (?, ?, ?, 1, ?)",
                        (username, p_hash, salt_hex, time.time()),
                    )
            conn.commit()

    def check_rate_limit(self, identifier: str, max_attempts: int = 5, window_seconds: float = 300.0) -> bool:
        now = time.time()
        attempts = self._failed_attempts.get(identifier, [])
        attempts = [t for t in attempts if now - t < window_seconds]
        self._failed_attempts[identifier] = attempts
        return len(attempts) < max_attempts

    def record_failed_attempt(self, identifier: str) -> None:
        now = time.time()
        attempts = self._failed_attempts.get(identifier, [])
        attempts.append(now)
        self._failed_attempts[identifier] = attempts

    def reset_failed_attempts(self, identifier: str) -> None:
        self._failed_attempts.pop(identifier, None)

    def authenticate(self, username: str, password: str, client_ip: str) -> str | None:
        if not self.check_rate_limit(client_ip) or not self.check_rate_limit(username):
            return None

        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if not row:
                self.record_failed_attempt(client_ip)
                self.record_failed_attempt(username)
                return None

            expected_hash = self._hash_password(password, row["salt"])
            if not hmac.compare_digest(row["password_hash"], expected_hash):
                self.record_failed_attempt(client_ip)
                self.record_failed_attempt(username)
                return None

            self.reset_failed_attempts(client_ip)
            self.reset_failed_attempts(username)

            token = secrets.token_urlsafe(32)
            expires_at = time.time() + (86400 * 7)
            conn.execute(
                "INSERT INTO sessions (token, username, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token, username, expires_at, time.time()),
            )
            conn.commit()
            return token

    def validate_session(self, token: str) -> User | None:
        now = time.time()
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT s.username, s.expires_at, u.id, u.is_admin, u.created_at "
                "FROM sessions s JOIN users u ON s.username = u.username "
                "WHERE s.token = ?",
                (token,),
            )
            row = cur.fetchone()
            if not row:
                return None
            if row["expires_at"] < now:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
            return User(
                id=row["id"],
                username=row["username"],
                is_admin=bool(row["is_admin"]),
                created_at=row["created_at"],
            )

    def revoke_session(self, token: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()


auth_manager = AuthManager()
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    token = None
    if credentials:
        token = credentials.credentials
    elif "session_token" in request.cookies:
        token = request.cookies.get("session_token")
    elif "authorization" in request.headers:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_manager.validate_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
