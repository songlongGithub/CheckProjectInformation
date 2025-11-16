"""
用户会话管理：负责在一次登录周期内缓存 Excel 解析结果与最新比对记录。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional


@dataclass
class SessionState:
    excel_data: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    excel_sheet_order: List[str] = field(default_factory=list)
    last_excel_filename: Optional[str] = None
    last_excel_uploaded_at: Optional[str] = None
    latest_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "has_excel": bool(self.excel_data),
            "sheet_order": self.excel_sheet_order,
            "last_excel_filename": self.last_excel_filename,
            "last_excel_uploaded_at": self.last_excel_uploaded_at,
            "latest_results": self.latest_results,
        }


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = Lock()

    def _get_or_create(self, username: str) -> SessionState:
        with self._lock:
            state = self._sessions.get(username)
            if state is None:
                state = SessionState()
                self._sessions[username] = state
            return state

    def update_excel_payload(
        self,
        username: str,
        excel_data: Dict[str, Dict[str, List[str]]],
        sheet_order: List[str],
        filename: str,
    ) -> SessionState:
        state = self._get_or_create(username)
        state.excel_data = excel_data
        state.excel_sheet_order = sheet_order
        state.last_excel_filename = filename
        state.last_excel_uploaded_at = datetime.utcnow().isoformat() + "Z"
        return state

    def get_excel_payload(self, username: str) -> SessionState:
        return self._get_or_create(username)

    def update_results(self, username: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        state = self._get_or_create(username)
        state.latest_results = results
        return results

    def reset(self, username: str) -> None:
        with self._lock:
            self._sessions.pop(username, None)


session_manager = SessionManager()

