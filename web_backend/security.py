"""
安全与令牌工具
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Optional


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """
    使用 PBKDF2 派生密码哈希，返回 base64 编码的 `salt:hash`.
    """
    if not password:
        raise ValueError("密码不能为空")
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 200_000)
    return f"{base64.b64encode(salt_bytes).decode()}:{base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """
    校验密码与已存储的 `salt:hash`.
    """
    try:
        salt_b64, digest_b64 = stored.split(":")
    except ValueError:
        return False
    salt_bytes = base64.b64decode(salt_b64)
    stored_digest = base64.b64decode(digest_b64)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 200_000)
    return hmac.compare_digest(stored_digest, candidate)


@dataclass
class TokenRecord:
    username: str
    expires_at: datetime


class TokenManager:
    """
    通过内存表维护 Bearer Token，支持有效期与快速失效。
    """

    def __init__(self, ttl_minutes: int = 240):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._tokens: Dict[str, TokenRecord] = {}
        self._lock = Lock()

    def create_token(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        record = TokenRecord(username=username, expires_at=datetime.utcnow() + self.ttl)
        with self._lock:
            self._tokens[token] = record
        return token

    def get_username(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self._lock:
            record = self._tokens.get(token)
            if not record:
                return None
            if record.expires_at < datetime.utcnow():
                self._tokens.pop(token, None)
                return None
            return record.username

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

