# -*- coding: utf-8 -*-
"""LLM 客户端抽象。

职责：
- 定义统一的 LLM 接口 complete_json(system, user) -> dict
- 提供 GeminiClient（默认）和 ClaudeClient 两种实现
- 隐藏各厂商 HTTP 协议细节，向上层暴露最小接口

设计理由：
- 不引入 google-genai / anthropic SDK，避免额外依赖（KISS）
- 强制 JSON 结构化输出，简化调用方解析
- 失败抛 LLMError，调用方据此决定降级策略
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import requests

from .logger import get_logger
from .rules import LLMCredentials

logger = get_logger(__name__)


class LLMError(Exception):
    """LLM 调用过程中的可预期错误"""


@dataclass
class LLMResult:
    """LLM 响应封装"""

    parsed: dict
    raw_text: str
    tokens_used: Optional[int] = None


class LLMClient(Protocol):
    """LLM 客户端契约：输入 system+user prompt，返回解析好的 JSON dict"""

    def complete_json(self, system: str, user: str) -> LLMResult:
        ...


# ---------- Gemini ----------
class GeminiClient:
    """Google Gemini REST API 客户端。

    默认模型 gemini-flash-latest（稳定、便宜、快）。
    """

    _ENDPOINT_TEMPLATE = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )

    def __init__(
        self,
        credentials: LLMCredentials,
        model: str = "gemini-flash-latest",
        timeout: float = 60.0,
        cache_dir: Optional[str | Path] = None,
    ):
        if not credentials or not credentials.api_key:
            raise ValueError("Gemini credentials with api_key are required")
        self._credentials = credentials
        self._model = model
        self._timeout = timeout
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def complete_json(self, system: str, user: str) -> LLMResult:
        """调用 Gemini 强制 JSON 输出。"""
        cache_hit = self._load_cache(system, user)
        if cache_hit is not None:
            logger.info(f"Gemini cache hit for model={self._model}.")
            return LLMResult(parsed=cache_hit["parsed"], raw_text=cache_hit["raw_text"])

        url = self._ENDPOINT_TEMPLATE.format(model=self._model)
        params = {"key": self._credentials.api_key}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        }

        try:
            resp = requests.post(url, params=params, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc

        raw_text = _extract_gemini_text(data)
        if not raw_text:
            raise LLMError(f"Gemini returned empty text. Raw: {json.dumps(data)[:300]}")

        parsed = _safe_json_loads(raw_text)
        self._save_cache(system, user, parsed, raw_text)
        return LLMResult(parsed=parsed, raw_text=raw_text)

    # ---------- 缓存（内容寻址）----------
    def _cache_key(self, system: str, user: str) -> str:
        digest = hashlib.sha256(
            f"{self._model}\0{system}\0{user}".encode("utf-8")
        ).hexdigest()
        return digest[:24]

    def _load_cache(self, system: str, user: str) -> Optional[dict]:
        if self._cache_dir is None:
            return None
        f = self._cache_dir / f"{self._cache_key(system, user)}.json"
        if not f.is_file():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"LLM cache read failed {f}: {exc}")
            return None

    def _save_cache(self, system: str, user: str, parsed: dict, raw_text: str) -> None:
        if self._cache_dir is None:
            return
        f = self._cache_dir / f"{self._cache_key(system, user)}.json"
        try:
            f.write_text(
                json.dumps({"parsed": parsed, "raw_text": raw_text}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"LLM cache write failed {f}: {exc}")


# ---------- Claude ----------
class ClaudeClient:
    """Anthropic Claude Messages API 客户端"""

    _ENDPOINT = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        credentials: LLMCredentials,
        model: str = "claude-haiku-4-5",
        timeout: float = 60.0,
        cache_dir: Optional[str | Path] = None,
    ):
        if not credentials or not credentials.api_key:
            raise ValueError("Claude credentials with api_key are required")
        self._credentials = credentials
        self._model = model
        self._timeout = timeout
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def complete_json(self, system: str, user: str) -> LLMResult:
        cache_hit = self._load_cache(system, user)
        if cache_hit is not None:
            logger.info(f"Claude cache hit for model={self._model}.")
            return LLMResult(parsed=cache_hit["parsed"], raw_text=cache_hit["raw_text"])

        headers = {
            "x-api-key": self._credentials.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 2048,
            "temperature": 0.1,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

        try:
            resp = requests.post(
                self._ENDPOINT, headers=headers, json=payload, timeout=self._timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise LLMError(f"Claude request failed: {exc}") from exc

        raw_text = _extract_claude_text(data)
        if not raw_text:
            raise LLMError(f"Claude returned empty text. Raw: {json.dumps(data)[:300]}")

        parsed = _safe_json_loads(raw_text)
        self._save_cache(system, user, parsed, raw_text)
        return LLMResult(parsed=parsed, raw_text=raw_text)

    def _cache_key(self, system: str, user: str) -> str:
        digest = hashlib.sha256(
            f"claude\0{self._model}\0{system}\0{user}".encode("utf-8")
        ).hexdigest()
        return digest[:24]

    def _load_cache(self, system: str, user: str) -> Optional[dict]:
        if self._cache_dir is None:
            return None
        f = self._cache_dir / f"{self._cache_key(system, user)}.json"
        if not f.is_file():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cache(self, system: str, user: str, parsed: dict, raw_text: str) -> None:
        if self._cache_dir is None:
            return
        f = self._cache_dir / f"{self._cache_key(system, user)}.json"
        try:
            f.write_text(
                json.dumps({"parsed": parsed, "raw_text": raw_text}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Claude cache write failed {f}: {exc}")


# ---------- Factory ----------
def build_llm_client(
    provider: str,
    credentials: Optional[LLMCredentials],
    model: Optional[str],
    cache_dir: Optional[str | Path] = None,
) -> Optional[LLMClient]:
    """构建 LLM 客户端。provider='none' 或凭据缺失返回 None。

    默认模型：
    - gemini → gemini-flash-latest
    - claude → claude-haiku-4-5
    """
    if provider in ("", "none", None) or credentials is None:
        return None

    if provider == "gemini":
        return GeminiClient(
            credentials=credentials,
            model=model or "gemini-flash-latest",
            cache_dir=cache_dir,
        )
    if provider == "claude":
        return ClaudeClient(
            credentials=credentials,
            model=model or "claude-haiku-4-5",
            cache_dir=cache_dir,
        )
    logger.warning(f"Unsupported LLM provider '{provider}', returning None.")
    return None


# ---------- 工具函数 ----------
def _extract_gemini_text(data: dict) -> str:
    """从 Gemini 响应里拼接所有 text part"""
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    except Exception as exc:
        logger.warning(f"Failed to parse Gemini response: {exc}")
        return ""


def _extract_claude_text(data: dict) -> str:
    """从 Claude 响应里拼接所有 text 块"""
    try:
        content = data.get("content", [])
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    except Exception as exc:
        logger.warning(f"Failed to parse Claude response: {exc}")
        return ""


def _safe_json_loads(text: str) -> dict:
    """尽力解析 JSON，支持剥离代码块标记"""
    stripped = text.strip()
    # 去掉 ```json ... ``` 围栏
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # 去首行围栏
        lines = lines[1:]
        # 去尾行围栏（若有）
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM output is not valid JSON: {exc}. Raw text: {text[:300]}") from exc
