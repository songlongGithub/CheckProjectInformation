"""
后台服务：封装 Excel 解析与 OCR 比对逻辑，供 FastAPI 直接调用。
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import logic
from excel_parser import MedicalExamParser

logger = logging.getLogger(__name__)


@dataclass
class ExcelParseResult:
    excel_data: Dict[str, Dict[str, List[str]]]
    sheet_order: List[str]
    scheme_names: List[str]
    scheme_catalog: List[Dict[str, Any]]


@dataclass
class OCRImage:
    path: str
    name: str


def _normalize_excel_projects(categorized: Dict[str, Dict[str, List[Dict]]]) -> Dict[str, Dict[str, List[str]]]:
    """
    将 parser 输出的富信息降维为 sheet/category -> 项目列表。
    """
    simple_data: Dict[str, Dict[str, List[str]]] = {}
    for scheme_name, categories in categorized.items():
        simple_data[scheme_name] = {}
        for category_name, projects in categories.items():
            deduped = list({p["full_name"]: p for p in projects}.values())
            sorted_projects = sorted(deduped, key=lambda item: item["row_index"])
            simple_data[scheme_name][category_name] = [p["full_name"] for p in sorted_projects]
    return simple_data


def parse_excel_file(excel_file: Path, rename_rules: List[List[str]], gender_rules: List[List[str]]) -> ExcelParseResult:
    parser = MedicalExamParser(str(excel_file))
    if rename_rules:
        parser.build_rename_map(rename_rules)
    parser.read_excel_data()
    categorized = parser.categorize_projects_by_gender_and_marital_status()
    if gender_rules:
        parser.build_gender_rename_map(gender_rules)
        parser._apply_gender_renames(categorized)
    excel_data = _normalize_excel_projects(categorized)
    scheme_catalog: List[Dict[str, Any]] = []
    scheme_names: List[str] = []
    for sheet_name in parser.sheet_names_in_order:
        categories = excel_data.get(sheet_name, {})
        for display_category in ["男", "女未婚", "女已婚", "女已婚检查H"]:
            items = categories.get(display_category)
            if not items:
                continue
            scheme_title = f"{sheet_name} - {display_category}"
            scheme_names.append(scheme_title)
            scheme_catalog.append(
                {
                    "scheme": scheme_title,
                    "sheet": sheet_name,
                    "category": display_category,
                    "item_count": len(items),
                }
            )
    return ExcelParseResult(
        excel_data=excel_data,
        sheet_order=parser.sheet_names_in_order,
        scheme_names=scheme_names,
        scheme_catalog=scheme_catalog,
    )


def _build_scheme_lookup(excel_data: Dict[str, Dict[str, List[str]]]) -> Dict[str, List[str]]:
    lookup: Dict[str, List[str]] = {}
    for sheet, categories in excel_data.items():
        for category, items in categories.items():
            lookup[f"{sheet} - {category}"] = items
    return lookup


def _build_stats(comparison: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "matched": sum(1 for item in comparison if item["status"] == "匹配"),
        "missing": sum(1 for item in comparison if item["status"] == "缺失"),
        "extra": sum(1 for item in comparison if item["status"] == "多余"),
    }


def evaluate_ocr_payload(
    ocr_payload: List[Tuple[str, List[str]]],
    scheme_lookup: Dict[str, List[str]],
    alias_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    scheme_names = list(scheme_lookup.keys())
    results: List[Dict[str, Any]] = []
    for ocr_title, ocr_items in ocr_payload:
        display_title = ocr_title or "未识别标题"
        matched = logic.find_best_match(ocr_title, scheme_names) if ocr_title else None
        if not matched:
            results.append(
                {
                    "ocr_title": display_title,
                    "matched_scheme": None,
                    "status": "unmatched",
                    "comparison": [],
                    "stats": {"matched": 0, "missing": 0, "extra": len(ocr_items)},
                    "extra_items": ocr_items,
                }
            )
            continue
        excel_items = scheme_lookup.get(matched, [])
        comparison = logic.generate_comparison_report(excel_items, ocr_items, alias_map)
        stats = _build_stats(comparison)
        status = "matched_perfect" if stats["missing"] == 0 and stats["extra"] == 0 else "matched_imperfect"
        results.append(
            {
                "ocr_title": display_title,
                "matched_scheme": matched,
                "status": status,
                "comparison": comparison,
                "stats": stats,
            }
        )
    return results


def process_images_with_ocr(
    images: List[OCRImage],
    api_key: str,
    secret_key: str,
    excel_data: Dict[str, Dict[str, List[str]]],
    alias_map: Dict[str, str],
    progress_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    if not api_key or not secret_key:
        raise ValueError("缺少百度OCR API密钥")
    if not excel_data:
        raise ValueError("请先上传并解析Excel方案后再执行OCR比对")
    scheme_lookup = _build_scheme_lookup(excel_data)
    access_token = logic.get_baidu_ocr_access_token(api_key, secret_key)
    if not access_token:
        raise RuntimeError("获取百度OCR Access Token失败，请检查密钥配置")

    report: List[Dict[str, Any]] = []
    stage_totals = {"ocr_request": 0.0, "json_parse": 0.0, "comparison": 0.0}
    for idx, image in enumerate(images, start=1):
        item_result: Dict[str, Any] = {
            "image_name": image.name,
            "index": idx,
            "total": len(images),
            "schemes": [],
            "errors": [],
        }
        stage_spent: Dict[str, float] = {}
        try:
            start = time.perf_counter()
            ocr_json = logic.get_ocr_result_from_baidu(access_token, image.path)
            stage_spent["ocr_request"] = time.perf_counter() - start
            if not ocr_json:
                item_result["errors"].append("OCR无响应")
            else:
                start = time.perf_counter()
                schemes = logic.extract_data_from_ocr_json(ocr_json)
                stage_spent["json_parse"] = time.perf_counter() - start
                if not schemes:
                    item_result["errors"].append("未识别到方案或项目")
                else:
                    start = time.perf_counter()
                    comparisons = evaluate_ocr_payload(schemes, scheme_lookup, alias_map)
                    stage_spent["comparison"] = time.perf_counter() - start
                    item_result["schemes"] = comparisons
        except Exception as exc:  # noqa: BLE001
            item_result["errors"].append(str(exc))
        else:
            for key, value in stage_spent.items():
                stage_totals[key] = stage_totals.get(key, 0.0) + value
            if stage_spent:
                dominant = max(stage_spent.items(), key=lambda item: item[1])
                detail = ", ".join(f"{k}={v:.2f}s" for k, v in stage_spent.items())
                logger.info("OCR耗时 image=%s [%s] | 最慢阶段=%s %.2fs", image.name, detail, dominant[0], dominant[1])
        report.append(item_result)
        if progress_callback:
            progress_callback([*report])
    if any(stage_totals.values()):
        slowest = max(stage_totals.items(), key=lambda item: item[1])
        total_detail = ", ".join(f"{k}={v:.2f}s" for k, v in stage_totals.items())
        logger.info("OCR总耗时统计 [%s] | 累计最慢阶段=%s %.2fs", total_detail, slowest[0], slowest[1])
    return report


def persist_upload(temp_dir: Path, filename: str, content: bytes) -> OCRImage:
    suffix = Path(filename).suffix or ".bin"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir)
    with handle:
        handle.write(content)
    return OCRImage(path=handle.name, name=filename or Path(handle.name).name)


def cleanup_images(images: List[OCRImage]) -> None:
    for image in images:
        try:
            os.unlink(image.path)
        except OSError:
            continue
