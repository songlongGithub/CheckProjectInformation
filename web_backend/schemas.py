"""
FastAPI Pydantic 模型
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int = Field(default=240, ge=1)


class AliasRule(BaseModel):
    alias: str
    standard: str


class RenameRule(BaseModel):
    original: str
    new_names: str


class GenderRenameRule(BaseModel):
    original: str
    male: str
    female: str


class RulesPayload(BaseModel):
    aliases: List[AliasRule] = Field(default_factory=list)
    renames: List[RenameRule] = Field(default_factory=list)
    gender_renames: List[GenderRenameRule] = Field(default_factory=list)


class OcrSettingsPayload(BaseModel):
    api_key: str
    secret_key: str


class OcrSettingsResponse(BaseModel):
    api_key: str
    secret_key: str


class AccountUpdateRequest(BaseModel):
    username: str
    current_password: str
    new_password: str


class ExcelUploadResponse(BaseModel):
    sheet_order: List[str]
    scheme_catalog: List[Dict[str, Any]]


class ExcelStatusResponse(BaseModel):
    has_excel: bool
    sheet_order: List[str]
    last_excel_filename: Optional[str]
    last_excel_uploaded_at: Optional[str]


class OCRProcessResponse(BaseModel):
    report: List[Dict[str, Any]]


class ResultsResponse(BaseModel):
    results: List[Dict[str, Any]]


class SchemeDetailResponse(BaseModel):
    scheme: str
    items: List[str]
