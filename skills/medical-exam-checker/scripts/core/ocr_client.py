# -*- coding: utf-8 -*-
"""百度 OCR 客户端封装。

职责：
- 获取 access_token
- 调用 accurate_basic 识别图片
- 支持磁盘缓存（cache_dir 存在时，命中则跳过 API 调用）
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import requests

from .logger import get_logger
from .rules import Credentials

logger = get_logger(__name__)

_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"


class OCRError(Exception):
    """OCR 流程中所有可预期的业务错误"""


class BaiduOCRClient:
    """百度 OCR 轻封装。惰性获取 token，支持图片级缓存。"""

    def __init__(
        self,
        credentials: Credentials,
        cache_dir: Optional[str | Path] = None,
        timeout: float = 30.0,
    ):
        if not credentials or not credentials.api_key or not credentials.secret_key:
            raise ValueError("credentials with api_key and secret_key are required")
        self._credentials = credentials
        self._cache_dir: Optional[Path] = Path(cache_dir) if cache_dir else None
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout
        self._access_token: Optional[str] = None

    # ---------- Token ----------
    def _ensure_token(self) -> str:
        """惰性拿 token；失败抛 OCRError"""
        if self._access_token:
            return self._access_token
        params = {
            "grant_type": "client_credentials",
            "client_id": self._credentials.api_key,
            "client_secret": self._credentials.secret_key,
        }
        try:
            resp = requests.post(_TOKEN_URL, params=params, timeout=self._timeout)
            resp.raise_for_status()
            token = resp.json().get("access_token")
        except Exception as exc:
            logger.error(f"Failed to obtain access token: {exc}")
            raise OCRError(f"Failed to obtain Baidu OCR access token: {exc}") from exc
        if not token:
            raise OCRError("Baidu OCR token endpoint returned no access_token.")
        self._access_token = token
        logger.info("Baidu OCR access token acquired.")
        return token

    # ---------- 识别 ----------
    def recognize(self, image_path: str | Path) -> dict:
        """识别单张图片。返回百度 OCR 原始 JSON。

        行为：
        - 若 cache_dir 命中（文件存在且非空），直接读缓存
        - 否则调用 API，并在 cache_dir 存在时写回缓存
        """
        img_path = Path(image_path)
        if not img_path.is_file():
            raise FileNotFoundError(f"Image not found: {img_path}")

        cached = self._load_cache(img_path)
        if cached is not None:
            logger.info(f"Cache hit for image: {img_path.name}")
            return cached

        token = self._ensure_token()
        url = f"{_OCR_URL}?access_token={token}"
        with img_path.open("rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {"image": img_b64, "language_type": "CHN_ENG"}
        try:
            resp = requests.post(url, data=data, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.error(f"OCR API failed for {img_path.name}: {exc}")
            raise OCRError(f"OCR API failed for {img_path.name}: {exc}") from exc

        if "error_code" in payload:
            # 百度返回的业务错误
            err_msg = payload.get("error_msg") or "unknown"
            raise OCRError(f"Baidu OCR business error: {err_msg} ({payload.get('error_code')})")

        self._save_cache(img_path, payload)
        logger.info(f"OCR done: {img_path.name}, words={len(payload.get('words_result', []))}")
        return payload

    # ---------- 缓存 ----------
    def _cache_file_for(self, image_path: Path) -> Optional[Path]:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"{image_path.name}.json"

    def _load_cache(self, image_path: Path) -> Optional[dict]:
        cache_file = self._cache_file_for(image_path)
        if cache_file is None or not cache_file.is_file():
            return None
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Cache read failed for {cache_file}: {exc}")
            return None

    def _save_cache(self, image_path: Path, payload: dict) -> None:
        cache_file = self._cache_file_for(image_path)
        if cache_file is None:
            return
        try:
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"Cache write failed for {cache_file}: {exc}")
