import base64
import json
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set

import requests
from fuzzywuzzy import fuzz, process

_NOISE_PARENTHESES_KEYWORDS = (
    "不可",
    "禁止",
    "替检",
    "补检",
    "紫单",
    "见名单",
    "名单",
    "复检",
)


def _remove_noise_parentheses(text: str) -> str:
    """去除括号中仅包含提示/限制信息的部分，保留性别信息"""
    if not text:
        return ""

    def should_remove(segment: str) -> bool:
        has_noise = any(keyword in segment for keyword in _NOISE_PARENTHESES_KEYWORDS)
        has_category = any(flag in segment for flag in ("男", "女", "未婚", "已婚"))
        return has_noise and not has_category

    def repl(match: re.Match) -> str:
        segment = match.group(0)
        return "" if should_remove(segment) else segment

    cleaned = re.sub(r"[（\(][^（）\(\)]*[）\)]", repl, text)

    # 处理缺少右括号的尾部片段，如“（紫单不可替...”
    tail_pattern = re.compile(r"[（\(][^（）\(\)]*$")
    while True:
        tail_match = tail_pattern.search(cleaned)
        if not tail_match:
            break
        segment = tail_match.group(0)
        if should_remove(segment):
            cleaned = cleaned[: tail_match.start()]
        else:
            break

    return cleaned.strip()

# --- [函数 1] 组件化精确匹配的“净化器” (无变化) ---
def normalize_for_precise_matching(text: str) -> str:
    """
    通过预定义的组件列表，强制将字符串拆分为正确的、独立的组件。
    """
    if not text:
        return ""
    
    processed_text = re.sub(r'[（()\-（）、_]', ' ', text)

    components = [
        '方案[一二三四五六七八九十]+',
        '女未婚', '女已婚',
        '心脑血管', '血糖', '肿瘤',
        '男', '女',
        '[A-Za-z0-9]+',
        '[\u4e00-\u9fa5]'
    ]
    regex = re.compile('|'.join(components))
    
    found_components = regex.findall(processed_text)

    return " ".join(filter(None, found_components)).lower()


# --- [函数 2] “分类器”辅助函数 (无变化) ---
def _extract_gender_marital_info(normalized_component_string: str) -> str:
    """
    从标准化的组件字符串中提取核心的性别和婚姻状态关键字。
    """
    text_for_keyword = normalized_component_string.replace(" ", "")
    if "女未婚" in text_for_keyword:
        return "女未婚"
    if "女已婚" in text_for_keyword:
        return "女已婚"
    if "男" in text_for_keyword:
        return "男"
    if "女" in text_for_keyword:
        return "女"
    return "通用"


# --- [函数 3] 最终修复版的智能精确匹配函数 (核心修改) ---
def find_best_match(ocr_title: str, scheme_names: List[str]) -> Optional[str]:
    """
    最终修复版：
    1. 分类匹配：使用宽松的关键字规则筛选候选方案。
    2. 核心匹配：移除关键字后，对方案的核心名称进行精确比较。
    """
    if not ocr_title or not scheme_names:
        return None
    
    processed_ocr_title = _remove_noise_parentheses(ocr_title)
    print(f"Log: Matching OCR title '{processed_ocr_title or ocr_title}' against {len(scheme_names)} Excel scheme(s).")
    
    componentized_ocr_title = normalize_for_precise_matching(processed_ocr_title)
    ocr_keyword = _extract_gender_marital_info(componentized_ocr_title)
    
    # 移除关键字，得到OCR标题的“核心”部分
    # 注意：需要将关键字中的空格也移除，以匹配组件化的字符串
    ocr_core_name = componentized_ocr_title.replace(ocr_keyword.replace(" ", ""), "").strip()
    
    candidate_schemes = []
    for name in scheme_names:
        componentized_excel_name = normalize_for_precise_matching(name)
        excel_keyword = _extract_gender_marital_info(componentized_excel_name)
        
        # 步骤 1: 分类匹配
        is_category_match = False
        if ocr_keyword == "通用" or excel_keyword == "通用":
            is_category_match = True
        elif ocr_keyword in excel_keyword or excel_keyword in ocr_keyword:
            is_category_match = True
        
        if is_category_match:
            # 移除关键字，得到Excel标题的“核心”部分
            excel_core_name = componentized_excel_name.replace(excel_keyword.replace(" ", ""), "").strip()
            # 将原始名称和核心名称一起存入候选列表
            candidate_schemes.append({'original': name, 'core': excel_core_name})

    if not candidate_schemes:
        print(f"Log: No candidates found for OCR title '{ocr_title}' with keyword '{ocr_keyword}'")
        return None
        
    # 步骤 2: 核心匹配
    # 从候选列表中提取所有的“核心”名称用于比较
    core_name_choices = [c['core'] for c in candidate_schemes]
    
    # 使用严格的 token_sort_ratio 对“核心”名称进行比较
    best_match_core, score = process.extractOne(
        ocr_core_name,
        core_name_choices,
        scorer=fuzz.token_sort_ratio 
    )
    
    if score >= 95:
        # 找到了匹配的“核心”名称，现在需要反向查找它对应的原始Excel方案名
        for candidate in candidate_schemes:
            if candidate['core'] == best_match_core:
                print(f"Log: Matched OCR title '{ocr_title}' -> '{candidate['original']}' (score={score}).")
                return candidate['original']
        
    print(f"Log: No precise match found for '{ocr_title}'. Best core candidate '{best_match_core}' had score {score}.")
    return None

# ===================================================================
# 以下是您文件中原有的其他函数，保持不变
# ===================================================================

def get_baidu_ocr_access_token(api_key: str, secret_key: str) -> Optional[str]:
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    try:
        response = requests.post(url)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        print(f"Log: Error getting access token: {e}")
        return None

def get_ocr_result_from_baidu(access_token: str, image_path: str) -> Optional[dict]:
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token=" + access_token
    try:
        with open(image_path, 'rb') as f:
            img = base64.b64encode(f.read()).decode()
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"image": img, "language_type": "CHN_ENG"}
        response = requests.post(url, data=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Log: Error during OCR request for {image_path}: {e}")
        return None

def _is_single_scheme_format(words: List[str]) -> bool:
    """检测是否为单方案结构"""
    if any(("订单编码" in (w or "")) or ("分组编码" in (w or "")) for w in words):
        return True
    has_group_label = any("分组名称" in w for w in words if w)
    has_custom_section = any("自定义选项" in w for w in words if w)
    if not has_group_label and has_custom_section:
        return True
    for text in words:
        cleaned = text.replace(" ", "")
        if not cleaned:
            continue
        return bool(re.fullmatch(r"[>\d.]+", cleaned))
    return False


def _is_price_line(text: str) -> bool:
    """检测是否为价格行"""
    if not text:
        return False
    cleaned = text.replace("￥", "").replace(",", "").strip()
    return bool(re.fullmatch(r"\d+(\.\d+)?", cleaned))


def _parse_single_scheme(words: List[str]) -> List[Tuple[str, List[str]]]:
    """解析单方案结构"""
    title_idx = next((idx for idx, text in enumerate(words) if "方案" in text), None)
    if title_idx is None:
        print("Log: Single-scheme payload missing title.")
        return []
    title = words[title_idx].strip()
    start_idx = next((idx for idx, text in enumerate(words) if "自定义选项" in text), None)
    if start_idx is None:
        print("Log: Single-scheme payload missing '自定义选项' marker.")
        return [(title, [])]

    end_idx = next(
        (idx for idx, text in enumerate(words[start_idx + 1 :], start_idx + 1) if "分组信息" in text),
        len(words),
    )

    collect_start = start_idx + 1
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


def _normalize_segments(segments: List[str]) -> List[str]:
    """合并分段文本并按顿号拆分"""
    joined = "".join(segment.strip() for segment in segments if segment.strip())
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


def _trim_to_scheme_keyword(text: str) -> str:
    """从文本中截取首个“方案”及其后内容"""
    if not text:
        return ""
    idx = text.find("方案")
    return text[idx:] if idx != -1 else text


def _parse_multi_scheme(words: List[str]) -> List[Tuple[str, List[str]]]:
    """解析多方案结构"""
    schemes: List[Tuple[str, List[str]]] = []
    idx = 0
    total = len(words)
    while idx < total:
        text = words[idx]
        if "方案" not in text:
            idx += 1
            continue

        title_parts = [text.strip()]
        idx += 1

        # 收集可能拆行的标题碎片，例如“检)”之类的不含顿号的短文本
        while idx < total and "分组价格" not in words[idx]:
            fragment = words[idx].strip()
            if not fragment or "分组名称" in fragment:
                break
            if "方案" in fragment or ("、" not in fragment and len(fragment) <= 20):
                title_parts.append(fragment)
                idx += 1
            else:
                break

        # 移动到分组价格标记
        while idx < total and "分组价格" not in words[idx]:
            idx += 1

        title = "".join(title_parts).strip()
        if not title:
            print("Log: Missing scheme title.")
            continue
        if idx >= total:
            print(f"Log: Price marker missing for scheme '{title}'.")
            break

        idx += 1  # 跳过“分组价格”所在行
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
            print(f"Log: No project segments detected for scheme '{title}'.")

        schemes.append((_trim_to_scheme_keyword(title), _normalize_segments(segments)))

        while idx < total and "分组交费" in words[idx]:
            idx += 1
    return schemes


def extract_data_from_ocr_json(ocr_result: dict) -> List[Tuple[str, List[str]]]:
    words_result = ocr_result.get("words_result", [])
    if not words_result:
        print("Log: OCR returned empty words_result.")
        return []
    words = [entry.get("words", "").strip() for entry in words_result]
    if not any(words):
        print("Log: OCR words list empty after stripping.")
        return []
    if _is_single_scheme_format(words):
        schemes = _parse_single_scheme(words)
    else:
        schemes = _parse_multi_scheme(words)
    print(f"Log: Extracted {len(schemes)} scheme(s) from OCR payload.")
    for idx, (title, items) in enumerate(schemes, 1):
        print(f"Log: Scheme {idx} title=\"{title}\" item_count={len(items)}")
    if not schemes:
        print("Log: OCR words captured (first 30 lines):")
        for snippet in words[:30]:
            print(f"Log:   -> {snippet}")
    return schemes

def build_alias_map(alias_data: List[List[str]]) -> Dict[str, str]:
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    preferred: Set[str] = set()
    for item in alias_data:
        if len(item) != 2:
            continue
        alias, standard_name = (item[0] or "").strip(), (item[1] or "").strip()
        if not alias or not standard_name:
            continue
        if alias == standard_name:
            preferred.add(standard_name)
            continue
        preferred.add(standard_name)
        adjacency[alias].add(standard_name)
        adjacency[standard_name].add(alias)

    alias_map: Dict[str, str] = {}
    visited: Set[str] = set()

    def choose_canonical(component: Set[str]) -> str:
        preferred_terms = [term for term in component if term in preferred]
        candidates = preferred_terms or list(component)
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

    return alias_map

def generate_comparison_report(excel_master_list: List[str], ocr_projects: List[str], alias_map: Dict[str, str]) -> List[Dict]:
    def get_standard_name(term: str) -> str:
        return alias_map.get(term, term)
    remaining_ocr_projects = ocr_projects[:]
    report = []
    for excel_item in excel_master_list:
        if not remaining_ocr_projects:
            report.append({'excel_item': excel_item, 'ocr_item': '【缺失】', 'status': '缺失'})
            continue
        standard_excel_item = get_standard_name(excel_item)
        normalized_ocr_choices = {ocr_item: get_standard_name(ocr_item) for ocr_item in remaining_ocr_projects}
        best_match_normalized, score = process.extractOne(standard_excel_item, normalized_ocr_choices.values(), scorer=fuzz.ratio)
        if score >= 85:
            original_ocr_item = ""
            for original, normalized in normalized_ocr_choices.items():
                if normalized == best_match_normalized:
                    original_ocr_item = original
                    break
            match_type = 'exact' if excel_item == original_ocr_item else 'alias'
            report.append({
                'excel_item': excel_item,
                'ocr_item': original_ocr_item,
                'status': '匹配',
                'match_type': match_type
            })
            remaining_ocr_projects.remove(original_ocr_item)
        else:
            report.append({
                'excel_item': excel_item,
                'ocr_item': '【缺失】',
                'status': '缺失'
            })
    for ocr_item in remaining_ocr_projects:
        report.append({
            'excel_item': '【多余】',
            'ocr_item': ocr_item,
            'status': '多余'
        })
    return report
