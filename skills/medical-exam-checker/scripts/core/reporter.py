# -*- coding: utf-8 -*-
"""报告生成模块：构建 JSON 契约 + 渲染 Markdown。

JSON 契约：
{
  "excel": {
    "file": "...",
    "sheets_in_order": [...],
    "schemes": [{"sheet", "category", "items"}]
  },
  "images": [
    {
      "file": "xxx.jpg",
      "status": "ok | ocr_failed | no_scheme_detected",
      "error": null | str,
      "ocr_schemes": [
        {
          "index": 1,
          "ocr_title": "...",
          "matched_excel_scheme": "..." | null,
          "confidence": int | null,
          "verdict": "perfect | partial | no_match",
          "stats": {"matched", "missing", "extra", "total_excel", "total_ocr"},
          "comparison": [{"excel", "ocr", "status", "match_type"}, ...]
        }
      ]
    }
  ],
  "summary": {...}
}
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional

from .excel_parser import Scheme
from .matcher import ComparisonRow


# ---------- JSON 构建 ----------
def build_image_result_ok(
    image_path: str,
    ocr_scheme_results: List[Dict],
) -> Dict:
    """构造单张图片成功处理的结果"""
    return {
        "file": os.path.basename(image_path),
        "path": image_path,
        "status": "ok" if ocr_scheme_results else "no_scheme_detected",
        "error": None if ocr_scheme_results else "OCR returned no scheme.",
        "ocr_schemes": ocr_scheme_results,
    }


def build_image_result_failed(image_path: str, error: str) -> Dict:
    """构造单张图片失败的结果（OCR 调用失败或响应异常）"""
    return {
        "file": os.path.basename(image_path),
        "path": image_path,
        "status": "ocr_failed",
        "error": error,
        "ocr_schemes": [],
    }


def build_ocr_scheme_result(
    index: int,
    ocr_title: str,
    ocr_items: List[str],
    matched_full_name: Optional[str],
    confidence: Optional[int],
    comparison_rows: Optional[List[ComparisonRow]],
    excel_items_count: int,
) -> Dict:
    """构造单个 OCR 方案的对比结果片段"""
    if matched_full_name is None:
        # 未匹配到 Excel 方案
        return {
            "index": index,
            "ocr_title": ocr_title,
            "matched_excel_scheme": None,
            "confidence": None,
            "verdict": "no_match",
            "stats": {
                "matched": 0,
                "missing": 0,
                "extra": len(ocr_items),
                "total_excel": 0,
                "total_ocr": len(ocr_items),
            },
            "comparison": [
                {"excel": "【多余】", "ocr": item, "status": "多余", "match_type": None}
                for item in ocr_items
            ],
        }

    rows = comparison_rows or []
    matched_count = sum(1 for r in rows if r.status == "匹配")
    missing_count = sum(1 for r in rows if r.status == "缺失")
    extra_count = sum(1 for r in rows if r.status == "多余")
    verdict = "perfect" if missing_count == 0 and extra_count == 0 else "partial"

    return {
        "index": index,
        "ocr_title": ocr_title,
        "matched_excel_scheme": matched_full_name,
        "confidence": confidence,
        "verdict": verdict,
        "stats": {
            "matched": matched_count,
            "missing": missing_count,
            "extra": extra_count,
            "total_excel": excel_items_count,
            "total_ocr": len(ocr_items),
        },
        "comparison": [
            {
                "excel": r.excel_item,
                "ocr": r.ocr_item,
                "status": r.status,
                "match_type": r.match_type,
                "reason": getattr(r, "reason", None),
            }
            for r in rows
        ],
    }


def build_report(
    excel_path: str,
    sheets_in_order: List[str],
    schemes: List[Scheme],
    image_results: List[Dict],
) -> Dict:
    """合成顶层报告 JSON"""
    # 汇总统计
    total_images = len(image_results)
    images_ok = sum(1 for r in image_results if r["status"] == "ok")
    images_ocr_failed = sum(1 for r in image_results if r["status"] == "ocr_failed")
    images_no_scheme = sum(1 for r in image_results if r["status"] == "no_scheme_detected")

    perfect = partial_ = no_match_ = 0
    for r in image_results:
        for os_ in r.get("ocr_schemes", []):
            v = os_.get("verdict")
            if v == "perfect":
                perfect += 1
            elif v == "partial":
                partial_ += 1
            elif v == "no_match":
                no_match_ += 1

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "excel": {
            "file": excel_path,
            "sheets_in_order": sheets_in_order,
            "schemes": [
                {"sheet": s.sheet, "category": s.category, "items": s.items}
                for s in schemes
            ],
        },
        "images": image_results,
        "summary": {
            "total_images": total_images,
            "images_ok": images_ok,
            "images_ocr_failed": images_ocr_failed,
            "images_no_scheme": images_no_scheme,
            "perfect_matches": perfect,
            "partial_matches": partial_,
            "no_match_schemes": no_match_,
        },
    }


# ---------- Markdown 渲染 ----------
_STATUS_ICON = {
    "匹配": "✅",
    "缺失": "❌",
    "多余": "⚠️",
}

_VERDICT_LABEL = {
    "perfect": "✅ 完美匹配",
    "partial": "⚠️ 部分匹配",
    "no_match": "❌ 未匹配到方案",
}


def render_markdown(report: Dict) -> str:
    """把 JSON 报告渲染为人类可读的 Markdown"""
    excel_info = report.get("excel", {})
    summary = report.get("summary", {})
    lines: List[str] = []

    lines.append("# 体检方案核对报告")
    lines.append("")
    lines.append(f"- 生成时间: {report.get('generated_at', '')}")
    lines.append(f"- Excel 文件: `{excel_info.get('file', '')}`")
    lines.append(f"- 图片总数: {summary.get('total_images', 0)}")
    lines.append(
        f"- OCR: 成功 {summary.get('images_ok', 0)} / 失败 {summary.get('images_ocr_failed', 0)} / 无方案 {summary.get('images_no_scheme', 0)}"
    )
    lines.append(
        f"- 方案核对: 完美 {summary.get('perfect_matches', 0)} / 部分 {summary.get('partial_matches', 0)} / 未匹配 {summary.get('no_match_schemes', 0)}"
    )
    lines.append("")

    # Excel 方案概览
    lines.append("## Excel 方案概览")
    lines.append("")
    for scheme in excel_info.get("schemes", []):
        lines.append(f"- **{scheme['sheet']} - {scheme['category']}** ({len(scheme['items'])} 项)")
    lines.append("")

    # 每张图片逐一输出
    lines.append("## 图片核对结果")
    lines.append("")
    for idx, image_result in enumerate(report.get("images", []), 1):
        lines.extend(_render_image_block(idx, image_result))
        lines.append("")

    return "\n".join(lines)


def _render_image_block(img_index: int, image_result: Dict) -> List[str]:
    """渲染单张图片的结果块（支持一图多方案）"""
    lines: List[str] = []
    file_name = image_result.get("file", "")
    status = image_result.get("status", "")

    lines.append(f"### 图片 {img_index}: `{file_name}` [{status.upper()}]")
    lines.append("")

    if status == "ocr_failed":
        lines.append(f"> ❗ OCR 失败：{image_result.get('error', '未知错误')}")
        return lines

    ocr_schemes = image_result.get("ocr_schemes", [])
    if not ocr_schemes:
        lines.append("> ⚠️ 未识别到任何方案")
        return lines

    # 顶部摘要：一图多方案时按顺序列出
    summary_parts = []
    for s in ocr_schemes:
        title = s.get("ocr_title", "")
        matched = s.get("matched_excel_scheme")
        summary_parts.append(f"**{title}** → {matched or '未匹配'}")
    lines.append("识别出 " + str(len(ocr_schemes)) + " 个方案：" + "; ".join(summary_parts))
    lines.append("")

    # 逐个方案详情
    for scheme in ocr_schemes:
        lines.extend(_render_ocr_scheme(scheme))
        lines.append("")

    return lines


def _render_ocr_scheme(scheme: Dict) -> List[str]:
    """渲染单个 OCR 方案的详情"""
    lines: List[str] = []
    idx = scheme.get("index", "?")
    title = scheme.get("ocr_title", "")
    matched = scheme.get("matched_excel_scheme")
    confidence = scheme.get("confidence")
    verdict = scheme.get("verdict", "")
    stats = scheme.get("stats", {})

    header = f"#### ① 方案 {idx}: {title}"
    header = header.replace("① ", "")  # 去掉占位符
    # 构造带圆数字的标题（fallback：方案 1）
    circled = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 6: "⑥", 7: "⑦", 8: "⑧", 9: "⑨"}.get(
        idx, f"({idx})"
    )

    target = f" ↔ {matched} (置信度 {confidence})" if matched else ""
    lines.append(f"#### {circled} {title}{target}")
    lines.append("")
    lines.append(f"- 结果: {_VERDICT_LABEL.get(verdict, verdict)}")
    lines.append(
        f"- 统计: 匹配 {stats.get('matched', 0)} / 缺失 {stats.get('missing', 0)} / 多余 {stats.get('extra', 0)} "
        f"(Excel {stats.get('total_excel', 0)} vs OCR {stats.get('total_ocr', 0)})"
    )
    lines.append("")

    comparison = scheme.get("comparison", [])
    if not comparison:
        return lines

    lines.append("| Excel 项 | OCR 项 | 状态 | 说明 |")
    lines.append("|---|---|---|---|")
    # 排序：匹配 → 缺失 → 多余
    order = {"匹配": 0, "缺失": 1, "多余": 2}
    sorted_rows = sorted(comparison, key=lambda r: order.get(r.get("status"), 99))
    for row in sorted_rows:
        icon = _STATUS_ICON.get(row.get("status"), "")
        match_type = row.get("match_type")
        reason = row.get("reason") or ""
        status_cell = f"{icon} {row.get('status')}"
        if row.get("status") == "匹配":
            if match_type == "alias":
                status_cell += "（别名）"
            elif match_type == "fuzzy":
                status_cell += "（模糊）"
            elif match_type == "llm":
                status_cell += "（语义）"
            elif match_type == "composite":
                status_cell += "（父项覆盖）"
        # 说明列：优先用 reason；表格单元格内禁用竖线
        note = reason.replace("|", "/")
        lines.append(
            f"| {row.get('excel', '')} | {row.get('ocr', '')} | {status_cell} | {note} |"
        )
    return lines
