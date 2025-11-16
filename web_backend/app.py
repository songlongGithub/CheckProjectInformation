"""
FastAPI 应用入口
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

import logic
from .config_manager import config_manager
from .schemas import (
    AccountUpdateRequest,
    ExcelStatusResponse,
    ExcelUploadResponse,
    LoginRequest,
    LoginResponse,
    OCRProcessResponse,
    OcrSettingsPayload,
    OcrSettingsResponse,
    ResultsResponse,
    RulesPayload,
    SchemeDetailResponse,
)
from .security import TokenManager, verify_password
from .session_manager import session_manager
from .services.comparison_service import (
    cleanup_images,
    parse_excel_file,
    persist_upload,
    process_images_with_ocr,
)

app = FastAPI(title="Medical Exam Checker Web", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

token_manager = TokenManager(ttl_minutes=240)
bearer_auth = HTTPBearer(auto_error=False)


def _rules_to_payload(rules_dict: dict) -> RulesPayload:
    aliases = [
        {"alias": item[0], "standard": item[1]}
        for item in rules_dict.get("aliases", [])
        if len(item) == 2 and item[0] and item[1]
    ]
    renames = [
        {"original": item[0], "new_names": item[1]}
        for item in rules_dict.get("renames", [])
        if len(item) == 2
    ]
    gender = [
        {"original": item[0], "male": item[1], "female": item[2]}
        for item in rules_dict.get("gender_renames", [])
        if len(item) == 3
    ]
    return RulesPayload(aliases=aliases, renames=renames, gender_renames=gender)


def _payload_to_rules(payload: RulesPayload) -> dict:
    return {
        "aliases": [[rule.alias.strip(), rule.standard.strip()] for rule in payload.aliases if rule.alias and rule.standard],
        "renames": [[rule.original.strip(), rule.new_names.strip()] for rule in payload.renames if rule.original],
        "gender_renames": [
            [rule.original.strip(), rule.male.strip(), rule.female.strip()]
            for rule in payload.gender_renames
            if rule.original
        ],
    }


def _get_credentials(credentials: HTTPAuthorizationCredentials = Depends(bearer_auth)) -> HTTPAuthorizationCredentials:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少授权信息")
    return credentials


def get_current_username(credentials: HTTPAuthorizationCredentials = Depends(_get_credentials)) -> str:
    username = token_manager.get_username(credentials.credentials)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="授权已失效，请重新登录")
    return username


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    users = config_manager.list_users()
    user = next((item for item in users if item["username"] == payload.username), None)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = token_manager.create_token(user["username"])
    return LoginResponse(access_token=token)


@app.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_get_credentials),
    username: str = Depends(get_current_username),
) -> dict:
    token_manager.revoke(credentials.credentials)
    session_manager.reset(username)
    return {"message": "已退出登录"}


@app.get("/api/settings/rules", response_model=RulesPayload)
def get_rules(username: str = Depends(get_current_username)) -> RulesPayload:
    rules = config_manager.get_rules_for_user(username)
    return _rules_to_payload(rules)


@app.put("/api/settings/rules", response_model=RulesPayload)
def update_rules(payload: RulesPayload, username: str = Depends(get_current_username)) -> RulesPayload:
    updated = config_manager.update_rules_for_user(username, _payload_to_rules(payload))
    return _rules_to_payload(updated)


@app.get("/api/settings/ocr", response_model=OcrSettingsResponse)
def get_ocr_settings(username: str = Depends(get_current_username)) -> OcrSettingsResponse:
    cfg = config_manager.get_ocr_for_user(username)
    return OcrSettingsResponse(api_key=cfg.get("api_key", ""), secret_key=cfg.get("secret_key", ""))


@app.put("/api/settings/ocr", response_model=OcrSettingsResponse)
def update_ocr_settings(payload: OcrSettingsPayload, username: str = Depends(get_current_username)) -> OcrSettingsResponse:
    updated = config_manager.update_ocr_for_user(username, payload.api_key, payload.secret_key)
    return OcrSettingsResponse(api_key=updated.get("api_key", ""), secret_key=updated.get("secret_key", ""))


@app.put("/api/settings/account")
def update_account(payload: AccountUpdateRequest, username: str = Depends(get_current_username)) -> dict:
    current_user = config_manager.get_user(username)
    if not current_user or not verify_password(payload.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前密码不正确")
    config_manager.replace_user(username, payload.username, payload.new_password)
    return {"message": "账号已更新，请重新登录"}


@app.post("/api/excel/upload", response_model=ExcelUploadResponse)
async def upload_excel(
    file: UploadFile = File(...),
    username: str = Depends(get_current_username),
) -> ExcelUploadResponse:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Excel 文件内容为空")
    suffix = Path(file.filename or "excel.xlsx").suffix or ".xlsx"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.write(contents)
    temp_file.flush()
    temp_file.close()
    try:
        rules = config_manager.get_rules_for_user(username)
        result = parse_excel_file(Path(temp_file.name), rules.get("renames", []), rules.get("gender_renames", []))
        session_manager.update_excel_payload(username, result.excel_data, result.sheet_order, file.filename or "方案.xlsx")
        return ExcelUploadResponse(sheet_order=result.sheet_order, scheme_catalog=result.scheme_catalog)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        Path(temp_file.name).unlink(missing_ok=True)


@app.get("/api/excel/status", response_model=ExcelStatusResponse)
def excel_status(username: str = Depends(get_current_username)) -> ExcelStatusResponse:
    state = session_manager.get_excel_payload(username)
    return ExcelStatusResponse(
        has_excel=bool(state.excel_data),
        sheet_order=state.excel_sheet_order,
        last_excel_filename=state.last_excel_filename,
        last_excel_uploaded_at=state.last_excel_uploaded_at,
    )


@app.get("/api/excel/scheme", response_model=SchemeDetailResponse)
def excel_scheme_detail(
    name: str = Query(..., min_length=1, description="Sheet - Category 形式的方案名称"),
    username: str = Depends(get_current_username),
) -> SchemeDetailResponse:
    state = session_manager.get_excel_payload(username)
    if not state.excel_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未上传 Excel 方案")
    if " - " not in name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="方案名称格式不正确")
    sheet, category = (part.strip() for part in name.split(" - ", 1))
    items = state.excel_data.get(sheet, {}).get(category)
    if items is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应方案")
    return SchemeDetailResponse(scheme=name, items=items)


@app.post("/api/ocr/process", response_model=OCRProcessResponse)
async def process_ocr_images(
    files: List[UploadFile] = File(...),
    username: str = Depends(get_current_username),
) -> OCRProcessResponse:
    state = session_manager.get_excel_payload(username)
    if not state.excel_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传并解析Excel方案")
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供至少一张图片")
    ocr_cfg = config_manager.get_ocr_for_user(username)
    alias_map = logic.build_alias_map(config_manager.get_rules_for_user(username).get("aliases", []))
    temp_dir = Path(tempfile.mkdtemp(prefix="ocr_uploads_"))
    persisted = []
    try:
        for upload in files:
            data = await upload.read()
            if not data:
                continue
            persisted.append(persist_upload(temp_dir, upload.filename or "ocr.png", data))
        if not persisted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所有上传文件为空")

        session_manager.update_results(username, [])

        def publish_progress(partial: List[dict]) -> None:
            session_manager.update_results(username, partial)

        report = process_images_with_ocr(
            persisted,
            ocr_cfg.get("api_key", ""),
            ocr_cfg.get("secret_key", ""),
            state.excel_data,
            alias_map,
            progress_callback=publish_progress,
        )
        session_manager.update_results(username, report)
        return OCRProcessResponse(report=report)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    finally:
        cleanup_images(persisted)
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/api/results", response_model=ResultsResponse)
def latest_results(username: str = Depends(get_current_username)) -> ResultsResponse:
    state = session_manager.get_excel_payload(username)
    return ResultsResponse(results=state.latest_results)


frontend_dist = Path(__file__).resolve().parent.parent / "web_frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
