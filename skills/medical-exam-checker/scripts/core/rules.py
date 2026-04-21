# -*- coding: utf-8 -*-
"""规则与凭据加载模块。

职责：
- load_rules(path): 从 JSON 加载 aliases / renames / gender_renames / composites
- load_credentials(cli_api, cli_secret, credentials_path):
  按 "CLI 参数 > 环境变量 > 配置文件" 优先级解析百度 OCR 凭据
- load_llm_credentials(provider, cli_key, credentials_path):
  解析 LLM 凭据（Gemini / Claude），环境变量候选多个 key 名
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class Composite:
    """主项 + 子项的包含关系：父项匹配成功后，子项自动视为已覆盖。"""

    parent: str
    children: List[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Rules:
    """规则容器"""

    aliases: List[List[str]] = field(default_factory=list)         # [[alias, standard], ...]
    renames: List[List[str]] = field(default_factory=list)         # [[original, "new1,new2"], ...]
    gender_renames: List[List[str]] = field(default_factory=list)  # [[original, male, female], ...]
    composites: List[Composite] = field(default_factory=list)      # 主项 + 子项包含关系


@dataclass
class Credentials:
    """百度 OCR 凭据"""

    api_key: str
    secret_key: str


@dataclass
class LLMCredentials:
    """通用 LLM 凭据"""

    provider: str      # 'gemini' / 'claude'
    api_key: str


def load_rules(path: Optional[str | Path]) -> Rules:
    """加载规则文件。

    Args:
        path: JSON 文件路径；为 None 时返回空 Rules（即无别名/重命名）。

    Raises:
        FileNotFoundError / json.JSONDecodeError：path 指定但不可读/无法解析。
    """
    if path is None:
        logger.warning("No rules path provided, using empty rules.")
        return Rules()

    rules_path = Path(path)
    if not rules_path.is_file():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    logger.info(f"Loading rules from {rules_path}")
    with rules_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rules = Rules(
        aliases=_sanitize_pairs(data.get("aliases", []), expected_len=2),
        renames=_sanitize_pairs(data.get("renames", []), expected_len=2),
        gender_renames=_sanitize_pairs(data.get("gender_renames", []), expected_len=3),
        composites=_parse_composites(data.get("composites", [])),
    )
    logger.info(
        f"Rules loaded: aliases={len(rules.aliases)}, "
        f"renames={len(rules.renames)}, gender_renames={len(rules.gender_renames)}, "
        f"composites={len(rules.composites)}"
    )
    return rules


def _sanitize_pairs(raw: object, expected_len: int) -> List[List[str]]:
    """容错：过滤掉长度不符或非 list 的条目"""
    if not isinstance(raw, list):
        return []
    cleaned: List[List[str]] = []
    for item in raw:
        if isinstance(item, list) and len(item) == expected_len:
            cleaned.append([str(x) for x in item])
    return cleaned


def _parse_composites(raw: object) -> List[Composite]:
    """解析 composites 列表。容错跳过非法条目。

    合法形态：{"parent": "...", "children": ["..."], "note": "..."}
    """
    if not isinstance(raw, list):
        return []
    items: List[Composite] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        parent = str(entry.get("parent") or "").strip()
        children_raw = entry.get("children") or []
        if not parent or not isinstance(children_raw, list):
            continue
        children = [str(c).strip() for c in children_raw if str(c).strip()]
        if not children:
            continue
        note = str(entry.get("note") or "").strip()
        items.append(Composite(parent=parent, children=children, note=note))
    return items


# ---------- 百度 OCR 凭据 ----------
def load_credentials(
    cli_api_key: Optional[str],
    cli_secret_key: Optional[str],
    credentials_path: Optional[str | Path],
) -> Credentials:
    """按优先级加载 OCR 凭据：CLI > 环境变量 > 配置文件。

    Raises:
        ValueError: 三条通道都无法获得有效凭据时。
    """
    # 1. CLI
    if cli_api_key and cli_secret_key:
        logger.info("OCR credentials sourced from CLI arguments.")
        return Credentials(api_key=cli_api_key.strip(), secret_key=cli_secret_key.strip())

    # 2. 环境变量
    env_api = os.environ.get("OCR_API_KEY")
    env_secret = os.environ.get("OCR_SECRET_KEY")
    if env_api and env_secret:
        logger.info("OCR credentials sourced from environment variables.")
        return Credentials(api_key=env_api.strip(), secret_key=env_secret.strip())

    # 3. 配置文件
    if credentials_path:
        cred_path = Path(credentials_path)
        if cred_path.is_file():
            with cred_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            ocr = data.get("baidu_ocr", {})
            api_key = ocr.get("api_key")
            secret_key = ocr.get("secret_key")
            if api_key and secret_key:
                logger.info(f"OCR credentials sourced from file: {cred_path}")
                return Credentials(api_key=api_key.strip(), secret_key=secret_key.strip())

    raise ValueError(
        "No valid OCR credentials found. Provide via --api-key/--secret-key, "
        "OCR_API_KEY/OCR_SECRET_KEY env vars, or a credentials file "
        "with {'baidu_ocr': {'api_key': ..., 'secret_key': ...}}."
    )


# ---------- LLM 凭据 ----------
# provider → (环境变量候选列表, credentials.json 内字段名)
_LLM_ENV_MAP = {
    "gemini": (["GEMINI_API_KEY", "GOOGLE_API_KEY"], "gemini"),
    "claude": (["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"], "claude"),
}


def load_llm_credentials(
    provider: str,
    cli_key: Optional[str],
    credentials_path: Optional[str | Path],
) -> Optional[LLMCredentials]:
    """按优先级加载 LLM 凭据：CLI > 环境变量 > credentials.json。

    Args:
        provider: 'gemini' / 'claude' / 'none'
        cli_key: 命令行直接传入的 API Key（最高优先级）
        credentials_path: 凭据 JSON 文件；文件中结构 `{provider: {api_key: "..."}}`

    Returns:
        LLMCredentials 或 None（provider='none' 或找不到任何凭据）。找不到时返回 None
        而不是抛异常，便于调用方降级到"关闭 LLM 层"。
    """
    if provider not in _LLM_ENV_MAP:
        if provider not in ("", "none", None):
            logger.warning(f"Unknown LLM provider '{provider}', skipping LLM.")
        return None

    if cli_key:
        logger.info(f"LLM credentials ({provider}) sourced from CLI.")
        return LLMCredentials(provider=provider, api_key=cli_key.strip())

    env_keys, file_key = _LLM_ENV_MAP[provider]
    for env_name in env_keys:
        value = os.environ.get(env_name)
        if value:
            logger.info(f"LLM credentials ({provider}) sourced from env {env_name}.")
            return LLMCredentials(provider=provider, api_key=value.strip())

    if credentials_path:
        cred_path = Path(credentials_path)
        if cred_path.is_file():
            try:
                with cred_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                block = data.get(file_key, {})
                api_key = block.get("api_key")
                if api_key:
                    logger.info(f"LLM credentials ({provider}) sourced from file: {cred_path}")
                    return LLMCredentials(provider=provider, api_key=str(api_key).strip())
            except Exception as exc:
                logger.warning(f"Failed to read LLM credentials from {cred_path}: {exc}")

    logger.info(f"No LLM credentials found for provider '{provider}'; LLM layer disabled.")
    return None


def default_rules_path() -> Path:
    """skill 内置的默认规则文件路径"""
    return Path(__file__).resolve().parent.parent.parent / "config" / "default_rules.json"


def default_credentials_path() -> Path:
    """skill 内置的默认凭据文件路径"""
    return Path(__file__).resolve().parent.parent.parent / "config" / "credentials.json"
