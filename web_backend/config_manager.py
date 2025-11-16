"""
配置管理：负责持久化账号、OCR 和规则设置。
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .security import hash_password

CONFIG_PATH = Path(__file__).resolve().parent / "web_settings.json"

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_default_rules() -> Dict[str, List[List[str]]]:
    """
    加载仓库中的 default_rules.json 作为默认值，若缺失则退化为最小集合。
    """
    fallback = {
        "aliases": [["静脉采血", "采血"], ["眼科常规", "眼科检查"], ["营养B餐", "标准早餐"]],
        "renames": [["一般检查", "身高体重,血压,放射项目不出胶片,超声项目不出片"]],
        "gender_renames": [["外科检查", "外科检查(男)", "外科检查(女)"]],
    }
    rules_file = PROJECT_ROOT / "default_rules.json"
    if not rules_file.exists():
        return fallback
    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "aliases": data.get("aliases", fallback["aliases"]),
            "renames": data.get("renames", fallback["renames"]),
            "gender_renames": data.get("gender_renames", fallback["gender_renames"]),
        }
    except Exception:
        return fallback


DEFAULT_RULES: Dict[str, List[List[str]]] = _load_default_rules()

DEFAULT_OCR: Dict[str, str] = {
    "api_key": os.getenv("MEC_DEFAULT_BAIDU_API_KEY", "DEMO_BAIDU_API_KEY"),
    "secret_key": os.getenv("MEC_DEFAULT_BAIDU_SECRET_KEY", "DEMO_BAIDU_SECRET"),
}

DEFAULT_USERS = [
    {
        "username": "admin",
        "password_hash": "S6tBiVb3pA2DPkwgQ8pwsA==:Dc+sTV4lIcy7sSQOtZUTXZ4PBWllYzN+6DNTIk3bBjU=",
    },
    {
        "username": "renyanan",
        "password_hash": "UP1qgtheZv02Jn1yejy9zw==:cHzxEEWR8pkSneYi4HNYwIyT1pSbOXRlTz4CJlZPd3E=",
    },
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "users": [
        {
            "username": user["username"],
            "password_hash": user["password_hash"],
            "rules": deepcopy(DEFAULT_RULES),
            "ocr": deepcopy(DEFAULT_OCR),
        }
        for user in DEFAULT_USERS
    ]
}


class ConfigManager:
    """
    线程安全的 JSON 配置读写器。
    """

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._lock = Lock()
        self._config = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write(DEFAULT_CONFIG)
            return deepcopy(DEFAULT_CONFIG)
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if self._migrate_structure(data):
            self._write(data)
        return data

    def _migrate_structure(self, data: Dict[str, Any]) -> bool:
        """
        旧版配置将 rules/ocr 放在顶层，此处迁移到用户级别。
        """
        changed = False
        legacy_rules = data.pop("rules", None)
        legacy_ocr = data.pop("ocr", None)
        for user in data.get("users", []):
            if "rules" not in user:
                user["rules"] = deepcopy(legacy_rules or DEFAULT_RULES)
                changed = True
            if "ocr" not in user:
                user["ocr"] = deepcopy(legacy_ocr or DEFAULT_OCR)
                changed = True
            if self._ensure_user_defaults(user):
                changed = True
        return changed

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save(self) -> None:
        self._write(self._config)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._config)

    # ----- 用户 -----
    def list_users(self) -> List[Dict[str, str]]:
        with self._lock:
            return deepcopy(self._config.get("users", []))

    def _get_user(self, username: str) -> Optional[Dict[str, Any]]:
        for user in self._config.get("users", []):
            if user["username"] == username:
                return user
        return None

    def _ensure_user_defaults(self, user: Dict[str, Any]) -> bool:
        updated = False
        rules = user.get("rules")
        if not rules or not any(rules.get(key) for key in ("aliases", "renames", "gender_renames")):
            user["rules"] = deepcopy(DEFAULT_RULES)
            updated = True
        ocr = user.get("ocr")
        if not ocr or not ocr.get("api_key") or not ocr.get("secret_key"):
            user["ocr"] = deepcopy(DEFAULT_OCR)
            updated = True
        return updated

    def _sync_rules_with_defaults(self, rules: Dict[str, List[List[str]]]) -> bool:
        """
        默认规则可能在仓库中更新，这里确保缺失的默认行会自动追加到用户配置中。
        """
        changed = False
        for key in ("aliases", "renames", "gender_renames"):
            user_rules = rules.setdefault(key, [])
            existing = {tuple(item) for item in user_rules if item}
            for default_item in DEFAULT_RULES.get(key, []):
                tpl = tuple(default_item)
                if tpl not in existing:
                    user_rules.append(list(default_item))
                    existing.add(tpl)
                    changed = True
        return changed

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            user = self._get_user(username)
            if user:
                if self._ensure_user_defaults(user):
                    self._save()
            return deepcopy(user) if user else None

    def replace_user(self, old_username: str, new_username: str, password: str) -> Dict[str, str]:
        hashed = hash_password(password)
        with self._lock:
            template_rules = deepcopy(DEFAULT_RULES)
            template_ocr = deepcopy(DEFAULT_OCR)
            existing = self._get_user(old_username)
            if existing:
                template_rules = deepcopy(existing.get("rules", DEFAULT_RULES))
                template_ocr = deepcopy(existing.get("ocr", DEFAULT_OCR))
            users = [user for user in self._config.setdefault("users", []) if user["username"] not in {old_username, new_username}]
            users.append(
                {
                    "username": new_username,
                    "password_hash": hashed,
                    "rules": template_rules,
                    "ocr": template_ocr,
                }
            )
            self._config["users"] = users
            self._save()
            return {"username": new_username}

    # ----- OCR & 规则按用户持久化 -----
    def get_rules_for_user(self, username: str) -> Dict[str, List[List[str]]]:
        with self._lock:
            user = self._get_user(username)
            if not user:
                raise KeyError(f"用户 {username} 不存在")
            changed = self._ensure_user_defaults(user)
            if self._sync_rules_with_defaults(user["rules"]):
                changed = True
            if changed:
                self._save()
            return deepcopy(user.get("rules", DEFAULT_RULES))

    def update_rules_for_user(self, username: str, rules: Dict[str, List[List[str]]]) -> Dict[str, List[List[str]]]:
        with self._lock:
            user = self._get_user(username)
            if not user:
                raise KeyError(f"用户 {username} 不存在")
            for key in ("aliases", "renames", "gender_renames"):
                rules.setdefault(key, [])
            user["rules"] = rules
            self._save()
            return deepcopy(user["rules"])

    def get_ocr_for_user(self, username: str) -> Dict[str, str]:
        with self._lock:
            user = self._get_user(username)
            if not user:
                raise KeyError(f"用户 {username} 不存在")
            if self._ensure_user_defaults(user):
                self._save()
            return deepcopy(user.get("ocr", DEFAULT_OCR))

    def update_ocr_for_user(self, username: str, api_key: str, secret_key: str) -> Dict[str, str]:
        with self._lock:
            user = self._get_user(username)
            if not user:
                raise KeyError(f"用户 {username} 不存在")
            user["ocr"] = {"api_key": api_key, "secret_key": secret_key}
            self._save()
            return deepcopy(user["ocr"])


config_manager = ConfigManager()
