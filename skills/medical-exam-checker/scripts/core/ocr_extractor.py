# -*- coding: utf-8 -*-
"""OCR JSON 抽取器：原始 words_result → [(title, items), ...]

保留原 logic.py 的识别规则：
- 单方案格式：订单编码/分组编码 / 无分组名称但有自定义选项 / 首个非空全由 '>0-9.' 构成
- 多方案格式：按每个含 '方案' 的行为分隔，用 '分组价格' → '分组交费' 区间收集项目
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class OCRScheme:
    """单个 OCR 方案（抽取结果）"""

    title: str
    items: List[str] = field(default_factory=list)


def extract_schemes(ocr_json: dict) -> List[OCRScheme]:
    """从百度 OCR 的原始 words_result 抽取方案列表。"""
    words_result = ocr_json.get("words_result") or []
    if not words_result:
        logger.warning("OCR payload has empty words_result.")
        return []

    words = [str(entry.get("words", "")).strip() for entry in words_result]
    if not any(words):
        logger.warning("OCR words list is empty after stripping.")
        return []

    raw_schemes: List[Tuple[str, List[str]]]
    if _is_single_scheme_format(words):
        raw_schemes = _parse_single_scheme(words)
    else:
        raw_schemes = _parse_multi_scheme(words)

    schemes = [OCRScheme(title=t, items=items) for t, items in raw_schemes]
    logger.info(f"Extracted {len(schemes)} scheme(s) from OCR payload.")
    for idx, s in enumerate(schemes, 1):
        logger.info(f"Scheme {idx} title='{s.title}' items={len(s.items)}")
    return schemes


# ---------- 单方案 vs 多方案判定 ----------
def _is_single_scheme_format(words: List[str]) -> bool:
    if any(("订单编码" in (w or "")) or ("分组编码" in (w or "")) for w in words):
        return True
    has_group_label = any("分组名称" in w for w in words if w)
    has_custom_section = any("自定义选项" in w for w in words if w)
    if not has_group_label and has_custom_section:
        return True
    # 首个非空 cleaned 文本全由 >, 数字, 点 构成 → 视为单方案样式
    for text in words:
        cleaned = text.replace(" ", "")
        if not cleaned:
            continue
        return bool(re.fullmatch(r"[>\d.]+", cleaned))
    return False


def _is_price_line(text: str) -> bool:
    if not text:
        return False
    cleaned = text.replace("￥", "").replace(",", "").strip()
    return bool(re.fullmatch(r"\d+(\.\d+)?", cleaned))


def _trim_to_scheme_keyword(text: str) -> str:
    """从文本截取首个 '方案' 及其后内容"""
    if not text:
        return ""
    idx = text.find("方案")
    return text[idx:] if idx != -1 else text


# ---------- 单方案解析 ----------
def _parse_single_scheme(words: List[str]) -> List[Tuple[str, List[str]]]:
    title_idx = next((i for i, t in enumerate(words) if "方案" in t), None)
    if title_idx is None:
        logger.warning("Single-scheme payload missing title.")
        return []
    title = words[title_idx].strip()

    start_idx = next((i for i, t in enumerate(words) if "自定义选项" in t), None)
    if start_idx is None:
        logger.warning("Single-scheme payload missing '自定义选项' marker.")
        return [(title, [])]

    end_idx = next(
        (i for i, t in enumerate(words[start_idx + 1 :], start_idx + 1) if "分组信息" in t),
        len(words),
    )

    collect_start = start_idx + 1
    # 若紧邻 1~3 行是以 '复' 开头的杂项，跳过
    lookahead = words[collect_start : collect_start + 3]
    for offset, candidate in enumerate(lookahead):
        snippet = (candidate or "").strip()
        if snippet.startswith("复"):
            collect_start += offset + 1
            break

    items: List[str] = []
    for text in words[collect_start:end_idx]:
        value = text.strip()
        if not value:
            continue
        items.append(value)
    return [(_trim_to_scheme_keyword(title), items)]


# ---------- 多方案解析 ----------
def _parse_multi_scheme(words: List[str]) -> List[Tuple[str, List[str]]]:
    schemes: List[Tuple[str, List[str]]] = []
    idx = 0
    total = len(words)

    while idx < total:
        text = words[idx]
        if "方案" not in text:
            idx += 1
            continue

        # 收集标题碎片直到遇到 '分组价格' 或 '分组名称' 或长含顿号行
        title_parts = [text.strip()]
        idx += 1
        while idx < total and "分组价格" not in words[idx]:
            fragment = words[idx].strip()
            if not fragment or "分组名称" in fragment:
                break
            if "方案" in fragment or ("、" not in fragment and len(fragment) <= 20):
                title_parts.append(fragment)
                idx += 1
            else:
                break

        # 推进到 '分组价格'
        while idx < total and "分组价格" not in words[idx]:
            idx += 1

        title = "".join(title_parts).strip()
        if not title:
            logger.warning("Multi-scheme: missing title.")
            continue
        if idx >= total:
            logger.warning(f"Multi-scheme: price marker missing for '{title}'.")
            break

        idx += 1  # 跳过 '分组价格' 本行
        while idx < total and _is_price_line(words[idx]):
            idx += 1

        # 清理价格后的杂项提示
        while idx < total and words[idx].strip() in {"检)", "检）", "分组名称：", "单见名单不可替检)"}:
            idx += 1

        segments: List[str] = []
        collecting = False
        while idx < total and "分组交费" not in words[idx]:
            current = words[idx].strip()
            if current:
                if not collecting:
                    if "、" in current:
                        segments.append(current)
                        collecting = True
                else:
                    segments.append(current)
            idx += 1

        if not segments:
            logger.warning(f"Multi-scheme: no project segments for '{title}'.")

        schemes.append((_trim_to_scheme_keyword(title), _normalize_segments(segments)))

        # 跳过 '分组交费' 行本身
        while idx < total and "分组交费" in words[idx]:
            idx += 1

    return schemes


def _normalize_segments(segments: List[str]) -> List[str]:
    """合并所有片段后按顿号拆分"""
    joined = "".join(s.strip() for s in segments if s.strip())
    joined = joined.replace("，", "、")
    joined = re.sub(r"、{2,}", "、", joined).strip("、")
    if not joined:
        return []
    items: List[str] = []
    for piece in joined.split("、"):
        cleaned = piece.strip(" 、，。:：;；")
        if cleaned:
            items.append(cleaned)
    return items
