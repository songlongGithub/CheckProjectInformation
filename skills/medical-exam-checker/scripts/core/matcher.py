# -*- coding: utf-8 -*-
"""方案名匹配 + 项目逐项对比 + 别名等价类合并。

匹配流水线（compare_items）：
  L1 规则层：alias 归一 + 字符精确匹配             → match_type='exact'/'alias'
  L2 Fuzzy 层：fuzz.ratio ≥ 85                     → match_type='fuzzy'
  L3 Composites 展开：父项命中则子项自动覆盖         → match_type='composite'
  L4 LLM 层（可选，默认开启，兜底）：Gemini/Claude   → match_type='llm'，支持一对多
  L5 剩余：未匹配的 Excel 项 → 缺失；OCR 项 → 多余

方案名匹配保留原有两步法（分类筛选 + 核心名称 token_sort_ratio ≥ 95）。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from fuzzywuzzy import fuzz, process

from .logger import get_logger
from .llm_client import LLMClient, LLMError
from .rules import Composite

logger = get_logger(__name__)


# 阈值常量
SCHEME_MATCH_THRESHOLD = 95
ITEM_MATCH_THRESHOLD = 85
LLM_CONFIDENCE_THRESHOLD = 0.7

_NOISE_PARENTHESES_KEYWORDS = (
    "不可", "禁止", "替检", "补检", "紫单", "见名单", "名单", "复检",
)


@dataclass
class ComparisonRow:
    """逐项对比的一行结果"""

    excel_item: str
    ocr_item: str
    status: str            # '匹配' / '缺失' / '多余'
    match_type: Optional[str] = None  # 'exact'/'alias'/'fuzzy'/'llm'/'composite'
    reason: Optional[str] = None      # LLM 理由 / composite 父项说明


# ============================================================================
# 别名图谱
# ============================================================================
def build_alias_map(alias_data: List[List[str]]) -> Dict[str, str]:
    """别名对列表合并成等价类，每个成员映射到 canonical。"""
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    preferred: Set[str] = set()

    for item in alias_data:
        if len(item) != 2:
            continue
        alias = (item[0] or "").strip()
        standard = (item[1] or "").strip()
        if not alias or not standard:
            continue
        if alias == standard:
            preferred.add(standard)
            continue
        preferred.add(standard)
        adjacency[alias].add(standard)
        adjacency[standard].add(alias)

    alias_map: Dict[str, str] = {}
    visited: Set[str] = set()

    def choose_canonical(component: Set[str]) -> str:
        candidates = [t for t in component if t in preferred] or list(component)
        return min(candidates, key=lambda term: (len(term), term))

    for term in list(adjacency.keys()):
        if term in visited:
            continue
        queue = deque([term])
        component: Set[str] = set()
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in adjacency.get(current, ()):
                if neighbor not in visited:
                    queue.append(neighbor)
        canonical = choose_canonical(component)
        for member in component:
            alias_map[member] = canonical

    logger.info(f"Alias map built: {len(alias_map)} members.")
    return alias_map


# ============================================================================
# 方案名匹配
# ============================================================================
def _remove_noise_parentheses(text: str) -> str:
    """去除仅含提示/限制的括号，保留含性别/婚姻信息的括号"""
    if not text:
        return ""

    def should_remove(segment: str) -> bool:
        has_noise = any(kw in segment for kw in _NOISE_PARENTHESES_KEYWORDS)
        has_category = any(flag in segment for flag in ("男", "女", "未婚", "已婚"))
        return has_noise and not has_category

    def repl(match: re.Match) -> str:
        segment = match.group(0)
        return "" if should_remove(segment) else segment

    cleaned = re.sub(r"[（\(][^（）\(\)]*[）\)]", repl, text)

    tail_pattern = re.compile(r"[（\(][^（）\(\)]*$")
    while True:
        m = tail_pattern.search(cleaned)
        if not m:
            break
        segment = m.group(0)
        if should_remove(segment):
            cleaned = cleaned[: m.start()]
        else:
            break
    return cleaned.strip()


def _normalize_for_precise_matching(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(\d+)\s*[~～\-]\s*\1(?=岁)", r"\1", text)
    processed = re.sub(r"[（()\-（）、_]", " ", text)
    components = [
        r"方案[一二三四五六七八九十]+",
        r"女未婚", r"女已婚",
        r"心脑血管", r"血糖", r"肿瘤",
        r"男", r"女",
        r"[A-Za-z0-9]+",
        r"[\u4e00-\u9fa5]",
    ]
    regex = re.compile("|".join(components))
    found = regex.findall(processed)
    return " ".join(filter(None, found)).lower()


def _extract_gender_marital_info(componentized: str) -> str:
    t = componentized.replace(" ", "")
    if "女未婚" in t:
        return "女未婚"
    if "女已婚" in t:
        return "女已婚"
    if "男" in t:
        return "男"
    if "女" in t:
        return "女"
    return "通用"


def match_scheme_name(
    ocr_title: str, scheme_full_names: List[str]
) -> Optional[Tuple[str, int]]:
    """把 OCR 方案标题匹配到 Excel 方案全名。"""
    if not ocr_title or not scheme_full_names:
        return None

    processed_title = _remove_noise_parentheses(ocr_title)
    componentized_ocr = _normalize_for_precise_matching(processed_title)
    ocr_keyword = _extract_gender_marital_info(componentized_ocr)
    ocr_core = componentized_ocr.replace(ocr_keyword.replace(" ", ""), "").strip()

    candidates = []
    for name in scheme_full_names:
        comp = _normalize_for_precise_matching(name)
        kw = _extract_gender_marital_info(comp)
        if ocr_keyword == "通用" or kw == "通用":
            is_cat_match = True
        else:
            is_cat_match = (ocr_keyword in kw) or (kw in ocr_keyword)
        if not is_cat_match:
            continue
        core = comp.replace(kw.replace(" ", ""), "").strip()
        candidates.append({"original": name, "core": core})

    if not candidates:
        logger.info(f"No category-matched candidate for '{ocr_title}'.")
        return None

    core_choices = [c["core"] for c in candidates]
    best_core, score = process.extractOne(
        ocr_core, core_choices, scorer=fuzz.token_sort_ratio
    )

    if score >= SCHEME_MATCH_THRESHOLD:
        for c in candidates:
            if c["core"] == best_core:
                logger.info(f"Matched '{ocr_title}' -> '{c['original']}' (score={score}).")
                return c["original"], int(score)
    logger.info(f"No precise match for '{ocr_title}'. Best core '{best_core}' score={score}.")
    return None


# ============================================================================
# 逐项对比 —— 三层匹配 + composites 展开
# ============================================================================
def compare_items(
    excel_items: List[str],
    ocr_items: List[str],
    alias_map: Dict[str, str],
    composites: Optional[List[Composite]] = None,
    llm_client: Optional[LLMClient] = None,
) -> List[ComparisonRow]:
    """Excel × OCR 项目列表对比，返回细粒度对比行。

    调用顺序：alias/精确 → fuzzy → composites 展开 → LLM（含一对多）→ 剩余缺失/多余。
    composites 先于 LLM：业务规则显式声明的父-子关系优先级高于 LLM 启发式匹配，
    避免 LLM 把父项误匹配到某个子项、其余子项被判"多余"的情况。
    LLM 失败自动降级，不阻塞主流程。
    """
    def canon(term: str) -> str:
        return alias_map.get(term, term)

    excel_remaining = list(excel_items)
    ocr_remaining = list(ocr_items)
    rows: List[ComparisonRow] = []

    # ---------- L1: alias 归一 + 精确匹配 ----------
    rows_l1, excel_remaining, ocr_remaining = _match_exact(
        excel_remaining, ocr_remaining, canon
    )
    rows.extend(rows_l1)

    # ---------- L2: fuzzy 贪心 ----------
    rows_l2, excel_remaining, ocr_remaining = _match_fuzzy(
        excel_remaining, ocr_remaining, canon
    )
    rows.extend(rows_l2)

    # ---------- L3: composites 双向展开 ----------
    # 只要业务上 Excel 方案里有父项（全量 excel_items），双向吸收子项
    if composites:
        excel_items_set = set(excel_items)
        rows_l3, excel_remaining, ocr_remaining = _expand_composites(
            excel_remaining, ocr_remaining, composites, excel_items_set
        )
        rows.extend(rows_l3)

    # ---------- L4: LLM 语义（可选，兜底） ----------
    if llm_client is not None and (excel_remaining or ocr_remaining):
        try:
            rows_l4, excel_remaining, ocr_remaining = _match_by_llm(
                excel_remaining, ocr_remaining, llm_client
            )
            rows.extend(rows_l4)
        except LLMError as exc:
            logger.warning(f"LLM layer failed, fallback to rule-only: {exc}")
        except Exception as exc:
            logger.warning(f"LLM layer unexpected error, fallback: {exc}")

    # ---------- L5: 剩余判缺失/多余 ----------
    for item in excel_remaining:
        rows.append(ComparisonRow(excel_item=item, ocr_item="【缺失】", status="缺失"))
    for item in ocr_remaining:
        rows.append(ComparisonRow(excel_item="【多余】", ocr_item=item, status="多余"))

    return rows


# ---------- L1: alias 归一 + 字符等价 ----------
def _match_exact(
    excel_items: List[str],
    ocr_items: List[str],
    canon,
) -> Tuple[List[ComparisonRow], List[str], List[str]]:
    """canonical 归一后字符相等即命中"""
    rows: List[ComparisonRow] = []
    ocr_canon_index: Dict[str, List[int]] = defaultdict(list)
    for idx, o in enumerate(ocr_items):
        ocr_canon_index[canon(o)].append(idx)

    matched_ocr_idx: Set[int] = set()
    excel_remaining: List[str] = []

    for e in excel_items:
        key = canon(e)
        pool = ocr_canon_index.get(key, [])
        picked = -1
        for idx in pool:
            if idx not in matched_ocr_idx:
                picked = idx
                break
        if picked == -1:
            excel_remaining.append(e)
            continue
        matched_ocr_idx.add(picked)
        matched_original = ocr_items[picked]
        match_type = "exact" if e == matched_original else "alias"
        rows.append(
            ComparisonRow(
                excel_item=e,
                ocr_item=matched_original,
                status="匹配",
                match_type=match_type,
            )
        )

    ocr_remaining = [o for i, o in enumerate(ocr_items) if i not in matched_ocr_idx]
    return rows, excel_remaining, ocr_remaining


# ---------- L2: fuzzy 贪心 ----------
def _match_fuzzy(
    excel_items: List[str],
    ocr_items: List[str],
    canon,
) -> Tuple[List[ComparisonRow], List[str], List[str]]:
    rows: List[ComparisonRow] = []
    remaining_ocr = list(ocr_items)
    excel_remaining: List[str] = []

    for e in excel_items:
        if not remaining_ocr:
            excel_remaining.append(e)
            continue
        canonical_excel = canon(e)
        canonical_choices = {o: canon(o) for o in remaining_ocr}
        best_canonical, score = process.extractOne(
            canonical_excel, canonical_choices.values(), scorer=fuzz.ratio
        )
        if score >= ITEM_MATCH_THRESHOLD:
            matched_original = ""
            for original, canonical in canonical_choices.items():
                if canonical == best_canonical:
                    matched_original = original
                    break
            rows.append(
                ComparisonRow(
                    excel_item=e,
                    ocr_item=matched_original,
                    status="匹配",
                    match_type="fuzzy",
                )
            )
            remaining_ocr.remove(matched_original)
        else:
            excel_remaining.append(e)

    return rows, excel_remaining, remaining_ocr


# ---------- L3: LLM 语义 ----------
_LLM_SYSTEM_PROMPT = (
    "你是体检项目核对助手。"
    "输入两组项目（Excel 标准项 与 OCR 识别项），判断它们的语义映射。"
    "规则：\n"
    "1. 同义/别名 → 一对一匹配；\n"
    "2. 单个 OCR 项可覆盖多个 Excel 项（如 OCR '妇科检查' 覆盖 Excel '妇科检查' 和 '白带常规'）；\n"
    f"3. 只输出 confidence ≥ {LLM_CONFIDENCE_THRESHOLD} 的匹配；\n"
    "4. 严格 JSON 输出：\n"
    '{"matches":[{"excel":["..."],"ocr":"...","confidence":0.92,"reason":"简短中文理由"}],'
    '"excel_unmatched":["..."],"ocr_unmatched":["..."]}\n'
    "excel 字段必须是数组（即使单项也是数组）；除 JSON 外不要输出任何内容。"
)


def _match_by_llm(
    excel_items: List[str],
    ocr_items: List[str],
    client: LLMClient,
) -> Tuple[List[ComparisonRow], List[str], List[str]]:
    """把残差交给 LLM 做语义匹配"""
    if not excel_items and not ocr_items:
        return [], excel_items, ocr_items

    user_prompt = (
        f"Excel 残差（{len(excel_items)} 项）：\n"
        f"{json.dumps(excel_items, ensure_ascii=False)}\n\n"
        f"OCR 残差（{len(ocr_items)} 项）：\n"
        f"{json.dumps(ocr_items, ensure_ascii=False)}\n\n"
        "输出 JSON。"
    )

    result = client.complete_json(system=_LLM_SYSTEM_PROMPT, user=user_prompt)
    parsed = result.parsed or {}
    raw_matches = parsed.get("matches") or []

    rows: List[ComparisonRow] = []
    used_excel: Set[str] = set()
    used_ocr: Set[str] = set()

    for entry in raw_matches:
        if not isinstance(entry, dict):
            continue
        excel_list = entry.get("excel") or []
        if isinstance(excel_list, str):
            excel_list = [excel_list]
        ocr_name = entry.get("ocr")
        confidence = entry.get("confidence", 0)
        reason = (entry.get("reason") or "").strip()

        try:
            conf_val = float(confidence)
        except (TypeError, ValueError):
            conf_val = 0.0
        if conf_val < LLM_CONFIDENCE_THRESHOLD:
            continue
        if not ocr_name or ocr_name not in ocr_items or ocr_name in used_ocr:
            continue
        valid_excel = [e for e in excel_list if e in excel_items and e not in used_excel]
        if not valid_excel:
            continue

        used_ocr.add(ocr_name)
        for e in valid_excel:
            used_excel.add(e)
            full_reason = (
                f"LLM(conf={conf_val:.2f}): {reason}" if reason else f"LLM(conf={conf_val:.2f})"
            )
            rows.append(
                ComparisonRow(
                    excel_item=e,
                    ocr_item=ocr_name,
                    status="匹配",
                    match_type="llm",
                    reason=full_reason,
                )
            )

    excel_remaining = [e for e in excel_items if e not in used_excel]
    ocr_remaining = [o for o in ocr_items if o not in used_ocr]
    return rows, excel_remaining, ocr_remaining


# ---------- L4: composites 双向展开 ----------
def _expand_composites(
    excel_remaining: List[str],
    ocr_remaining: List[str],
    composites: List[Composite],
    excel_items_set: Set[str],
) -> Tuple[List[ComparisonRow], List[str], List[str]]:
    """composites 双向展开：只要父项业务上存在于 Excel 方案里，就触发吸收。

    - 方向 A：Excel 剩余里的子项 → 被父项覆盖（避免误报"缺失"）
    - 方向 B：OCR 剩余里的子项   → 被父项吸收（避免误报"多余"）；
              若 Excel 父项此时仍在 remaining 里（之前层级未命中），
              则同时把父项一并消费，记为父子匹配。

    仅当父项存在于 excel_items_set（Excel 方案全量清单）才生效，
    避免 OCR 单方面出现父项导致子项被错误吸收。

    Returns:
        (composite_rows, 新的 excel_remaining, 新的 ocr_remaining)
    """
    rows: List[ComparisonRow] = []
    parent_children: Dict[str, List[str]] = {c.parent: c.children for c in composites}
    notes: Dict[str, str] = {c.parent: c.note for c in composites}

    # 子 → 父 反向索引，加速查找
    child_to_parent: Dict[str, str] = {}
    for parent, children in parent_children.items():
        if parent not in excel_items_set:
            continue  # 父项业务上不存在 → 该 composite 规则此方案不激活
        for child in children:
            child_to_parent[child] = parent

    # 方向 A：Excel 剩余子项 → 被父项覆盖
    still_excel_remaining: List[str] = []
    for item in excel_remaining:
        parent = child_to_parent.get(item)
        if parent:
            note = notes.get(parent, "")
            reason = f"父项'{parent}'覆盖" + (f": {note}" if note else "")
            rows.append(
                ComparisonRow(
                    excel_item=item,
                    ocr_item=f"∈{parent}",
                    status="匹配",
                    match_type="composite",
                    reason=reason,
                )
            )
        else:
            still_excel_remaining.append(item)

    # 方向 B：OCR 剩余子项 → 被父项吸收
    # 若 Excel 父项仍在 still_excel_remaining（之前未被 L1-L3 命中），
    # 则把这次 OCR 子项识别直接作为"父-子"匹配并同时消费父项。
    still_ocr_remaining: List[str] = []
    excel_still_set = set(still_excel_remaining)
    for item in ocr_remaining:
        parent = child_to_parent.get(item)
        if not parent:
            still_ocr_remaining.append(item)
            continue
        note = notes.get(parent, "")
        if parent in excel_still_set:
            # Excel 父项尚未匹配 → 用这次 OCR 子项命中父项
            excel_still_set.remove(parent)
            reason = (
                f"OCR 子项'{item}'映射到 Excel 父项'{parent}'"
                + (f": {note}" if note else "")
            )
            rows.append(
                ComparisonRow(
                    excel_item=parent,
                    ocr_item=item,
                    status="匹配",
                    match_type="composite",
                    reason=reason,
                )
            )
        else:
            # Excel 父项已在之前层级匹配 → 子项额外吸收
            reason = f"被父项'{parent}'吸收" + (f": {note}" if note else "")
            rows.append(
                ComparisonRow(
                    excel_item=f"∈{parent}",
                    ocr_item=item,
                    status="匹配",
                    match_type="composite",
                    reason=reason,
                )
            )

    # 方向 B 可能消费掉的父项从 still_excel_remaining 中移除
    still_excel_remaining = [e for e in still_excel_remaining if e in excel_still_set]
    return rows, still_excel_remaining, still_ocr_remaining
