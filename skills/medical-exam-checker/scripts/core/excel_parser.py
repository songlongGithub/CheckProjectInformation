# -*- coding: utf-8 -*-
"""体检方案 Excel 解析模块。

输入：体检方案 xlsx + Rules（别名/重命名/性别重命名）
输出：List[Scheme]，每个 Scheme 表示一个 (sheet, category) 组合及其项目列表

核心设计点（保留原有算法，移除 GUI/QSettings 依赖）：
1. 状态机：按 A 列关键字切换男/女未婚/女已婚/女已婚H/女性通用/标准(NORMAL)
2. 组合模型：通用桶 + 专属桶组合；仅当专属桶非空才生成对应方案
3. 重命名：解析阶段应用；SELF 关键字表示保留原名
4. 性别重命名：分类后按 category 决定采用 male/female 版本
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

import pandas as pd

from .logger import get_logger
from .rules import Rules

logger = get_logger(__name__)


@dataclass
class Scheme:
    """解析后的方案单元"""

    sheet: str
    category: str  # '男' / '女未婚' / '女已婚' / '女已婚检查H'
    items: List[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        """用于方案名匹配的全名：'<sheet> - <category>'"""
        return f"{self.sheet} - {self.category}"


# 识别女性必须归已婚的关键字（仅对 FEMALE_GENERIC 区块生效）
_MARITAL_STATUS_KEYWORDS = [
    "妇科", "宫颈", "TCT", "HPV", "白带", "阴道",
    "子宫", "卵巢", "宫颈刮片", "妇检",
]

# 排除关键字：行中包含任一则丢弃
_EXCLUDED_KEYWORDS = [
    "健康管理", "套餐价格", "价格", "合计", "小计",
    "费用", "收费", "总计",
]

# 套餐关键字：触发"整组仅登记一次主项目名"
_PACKAGE_KEYWORDS = ["全套", "套餐", "肝功十三项", "肝功十一项"]

# 状态机触发词（注意：女已婚H 必须先于 女已婚 判断）
_STATE_TRIGGERS = [
    ("男性检查", "MALE"),
    ("女未婚检查", "FEMALE_UNMARRIED"),
    ("女已婚检查H", "FEMALE_MARRIED_H"),
    ("女已婚检查", "FEMALE_MARRIED"),
    ("女性检查", "FEMALE_GENERIC"),
    ("标准早餐", "NORMAL"),
]

# 行级纯标题检测用的名单
_HEADER_TITLES = {"男性检查", "女性检查", "女未婚检查", "女已婚检查", "女已婚检查H"}

# 输出类别固定顺序
_CATEGORY_ORDER = ["男", "女未婚", "女已婚", "女已婚检查H"]


class ExcelParser:
    """体检方案解析器（无 GUI 依赖）"""

    def __init__(self, excel_path: str, rules: Rules):
        """
        Args:
            excel_path: xlsx 文件路径
            rules: 解析阶段使用的重命名/性别重命名规则
        """
        if not excel_path:
            raise ValueError("excel_path must not be empty")

        self.excel_path = excel_path
        self.rules = rules
        self.schemes_data: Dict[str, List[Dict]] = {}
        self.sheet_names_in_order: List[str] = []
        self.sheet_name_alias_map: Dict[str, str] = {}

        # 从 Rules 构建运行时字典
        self.rename_map = self._build_rename_map(rules.renames)
        self.gender_rename_map = self._build_gender_rename_map(rules.gender_renames)

        # 默认：当行无 '√' 且当前区块是 NORMAL 时，项目视为男女通用
        self.default_to_universal_if_no_checkmark = True

    # ---------- 规则预处理 ----------
    @staticmethod
    def _build_rename_map(rename_data: List[List[str]]) -> Dict[str, List[str]]:
        """原名 → 拆分后的新名列表（逗号分隔）"""
        rename_map: Dict[str, List[str]] = {}
        for item in rename_data:
            if len(item) == 2 and item[0]:
                original, new_names_str = item
                rename_map[original] = [name.strip() for name in new_names_str.split(",") if name.strip()]
        logger.info(f"Built {len(rename_map)} rename rules.")
        return rename_map

    @staticmethod
    def _build_gender_rename_map(gender_data: List[List[str]]) -> Dict[str, Dict[str, str]]:
        """原名 → {'male': 男名, 'female': 女名}"""
        gender_map: Dict[str, Dict[str, str]] = {}
        for item in gender_data:
            if len(item) == 3 and item[0]:
                original, male_name, female_name = item
                gender_map[original] = {"male": male_name, "female": female_name}
        logger.info(f"Built {len(gender_map)} gender rename rules.")
        return gender_map

    # ---------- 对外主入口 ----------
    def parse(self) -> List[Scheme]:
        """执行完整解析流程，返回 Scheme 列表（按 sheet 原序 + category 固定序）"""
        self._read_excel()
        categorized = self._categorize()
        self._apply_gender_renames(categorized)
        return self._to_scheme_list(categorized)

    # ---------- 读取 Excel ----------
    def _read_excel(self) -> None:
        logger.info(f"Reading Excel file: {self.excel_path}")
        xls = pd.ExcelFile(self.excel_path)
        raw_sheet_names = xls.sheet_names

        self.sheet_names_in_order = []
        self.sheet_name_alias_map.clear()

        # 单 sheet 且名为 'Sheet' 时重命名展示为 '方案'
        if len(raw_sheet_names) == 1 and raw_sheet_names[0].strip().lower() == "sheet":
            display_name = "方案"
            self.sheet_names_in_order.append(display_name)
            self.sheet_name_alias_map[display_name] = raw_sheet_names[0]
        else:
            for name in raw_sheet_names:
                display_name = name.strip()
                self.sheet_names_in_order.append(display_name)
                self.sheet_name_alias_map[display_name] = name

        for sheet_name in self.sheet_names_in_order:
            actual_name = self.sheet_name_alias_map.get(sheet_name, sheet_name)
            logger.info(f"Processing sheet: {sheet_name}")

            tmp_df = pd.read_excel(xls, sheet_name=actual_name, nrows=1)
            num_cols = len(tmp_df.columns)
            use_cols = [0, 1, 2, 4, 5]
            valid_use_cols = [c for c in use_cols if c < num_cols]
            all_names = ["项目名称", "子项目", "内容明细", "男", "女"]
            actual_names = [all_names[i] for i in range(len(valid_use_cols))]

            df = pd.read_excel(
                xls,
                sheet_name=actual_name,
                header=None,
                usecols=valid_use_cols,
                names=actual_names,
            )
            for col_name in all_names:
                if col_name not in df.columns:
                    df[col_name] = ""
            projects = self._clean_and_filter_projects(df, sheet_name)
            self.schemes_data[sheet_name] = projects
            logger.info(f"Sheet '{sheet_name}' parsed: {len(projects)} valid projects.")

    # ---------- 单 sheet 清洗（核心状态机） ----------
    def _clean_and_filter_projects(self, df: pd.DataFrame, sheet_name: str) -> List[Dict]:
        """状态机驱动，识别项目、所属区块和性别归属"""
        projects: List[Dict] = []
        last_main_project_name = ""
        last_added_package_name = ""
        current_state = "NORMAL"
        data_started = False

        for index, row in df.iterrows():
            a = _safe_str(row["项目名称"])
            b = _safe_str(row["子项目"])
            c = _safe_str(row["内容明细"])

            # 数据起点：A 列出现 '项目或组合'（忽略空格）
            header_text = a.replace(" ", "")
            if header_text == "项目或组合":
                data_started = True
                continue
            if not data_started:
                continue

            # 遇到 '健康管理' 立即停止
            if a and "健康管理" in a:
                logger.debug("Encountered 健康管理 section, stop further rows.")
                break

            # 状态更新：整行（A+B）参与
            full_row_text = f"{a} {b}"
            new_state = _update_state(full_row_text)
            if new_state:
                current_state = new_state
                logger.debug(f"State -> {current_state} by '{full_row_text}'")

            # 纯标题行（A 有值、B/C 空、A 命中状态关键字） → 跳过
            is_pure_header = a and not b and not c and _update_state(a) is not None
            if is_pure_header:
                continue

            # 记录当前主项目名（A 列）
            if a:
                last_main_project_name = a
            if any(kw in last_main_project_name for kw in _EXCLUDED_KEYWORDS):
                continue

            # 智能选取最终项目名
            final_name = self._pick_final_name(
                a, b, last_main_project_name, last_added_package_name
            )
            if final_name is None:
                continue
            # 若触发的是套餐整合，则更新去重标记
            if any(kw in last_main_project_name for kw in _PACKAGE_KEYWORDS):
                last_added_package_name = last_main_project_name

            # 清洗 & 过滤标题回吞
            final_name = _normalize_item_name(final_name)
            if final_name in _HEADER_TITLES:
                continue
            if any(kw in final_name for kw in _EXCLUDED_KEYWORDS):
                continue

            # 性别归属：√ > 状态上下文 > NORMAL 默认通用
            has_male = _safe_str(row["男"]) == "√"
            has_female = _safe_str(row["女"]) == "√"
            is_for_male, is_for_female = self._infer_gender(
                has_male, has_female, current_state
            )

            base_project = {
                "project_name": last_main_project_name,
                "sub_project": b,
                "full_name": final_name,
                "details": c,
                "for_male": is_for_male,
                "for_female": is_for_female,
                "sheet_name": sheet_name,
                "row_index": index + 1,
                "category_hint": current_state,
            }

            # 应用重命名规则（可能拆成多个项目）
            if final_name in self.rename_map:
                new_names = self.rename_map[final_name]
                for i, new_name in enumerate(new_names):
                    resolved = final_name if new_name == "SELF" else new_name
                    new_p = base_project.copy()
                    new_p["full_name"] = resolved
                    new_p["row_index"] += i * 0.1  # 保持排序稳定
                    projects.append(new_p)
                continue

            projects.append(base_project)

        return projects

    @staticmethod
    def _pick_final_name(
        a: str, b: str, last_main: str, last_pkg: str
    ) -> str | None:
        """项目名选取优先级：套餐整合 > B 列子项目 > A 列主项目"""
        if any(kw in last_main for kw in _PACKAGE_KEYWORDS):
            if last_main != last_pkg:
                return last_main
            return None  # 同一套餐已登记过，跳过
        if b:
            return b
        if a:
            return a
        return None

    def _infer_gender(
        self, has_male: bool, has_female: bool, state: str
    ) -> tuple[bool, bool]:
        """性别归属三级优先"""
        if has_male or has_female:
            return has_male, has_female
        if state == "MALE":
            return True, False
        if state in ("FEMALE_UNMARRIED", "FEMALE_MARRIED", "FEMALE_MARRIED_H", "FEMALE_GENERIC"):
            return False, True
        if state == "NORMAL" and self.default_to_universal_if_no_checkmark:
            return True, True
        return False, False

    # ---------- 婚育豁免与识别 ----------
    @staticmethod
    def _is_universal_female_project(name: str) -> bool:
        """乳腺/盆腔彩超等，女性通用，不受婚育关键字影响"""
        return (
            (("乳腺" in name) and ("彩超" in name or "超声" in name))
            or (("盆腔" in name) and ("彩超" in name or "超声" in name))
        )

    def _identify_marital_status_projects(self) -> Set[str]:
        """扫描所有项目，找出婚育关键字命中项（仅对 FEMALE_GENERIC 区块使用）"""
        marital_set: Set[str] = set()
        for projects in self.schemes_data.values():
            for p in projects:
                if self._is_universal_female_project(p["full_name"]):
                    continue
                text = f"{p['project_name']} {p['sub_project']}"
                if any(kw in text for kw in _MARITAL_STATUS_KEYWORDS):
                    marital_set.add(p["full_name"])
        logger.info(f"Identified {len(marital_set)} marital-status projects.")
        return marital_set

    # ---------- 组合模型分类 ----------
    def _categorize(self) -> Dict[str, Dict[str, List[Dict]]]:
        marital_set = self._identify_marital_status_projects()
        out: Dict[str, Dict[str, List[Dict]]] = {}

        for s_name, projects in self.schemes_data.items():
            uni_male, uni_female = [], []
            block_male, block_fu, block_fm, block_fmh = [], [], [], []
            temp_fg: List[Dict] = []

            for p in projects:
                hint = p.get("category_hint", "NORMAL")
                if hint == "NORMAL":
                    if p["for_male"]:
                        uni_male.append(p.copy())
                    if p["for_female"]:
                        uni_female.append(p.copy())
                elif hint == "MALE" and p["for_male"]:
                    block_male.append(p.copy())
                elif hint == "FEMALE_UNMARRIED" and p["for_female"]:
                    block_fu.append(p.copy())
                elif hint == "FEMALE_MARRIED" and p["for_female"]:
                    block_fm.append(p.copy())
                elif hint == "FEMALE_MARRIED_H" and p["for_female"]:
                    block_fmh.append(p.copy())
                elif hint == "FEMALE_GENERIC" and p["for_female"]:
                    temp_fg.append(p.copy())

            # 女性通用区块：全部进已婚；剔除婚育项后再进未婚
            if temp_fg:
                logger.info(f"Processing FEMALE_GENERIC block for sheet '{s_name}'")
                block_fm.extend(item.copy() for item in temp_fg)
                non_marital = [p for p in temp_fg if p["full_name"] not in marital_set]
                block_fu.extend(item.copy() for item in non_marital)

            # 只有专属桶非空才生成对应组合
            out[s_name] = {}
            if block_male:
                out[s_name]["男"] = uni_male + block_male
            if block_fu:
                out[s_name]["女未婚"] = uni_female + block_fu
            if block_fm:
                out[s_name]["女已婚"] = uni_female + block_fm
            if block_fmh:
                out[s_name]["女已婚检查H"] = uni_female + block_fmh

        return out

    # ---------- 性别重命名 ----------
    def _apply_gender_renames(self, categorized: Dict[str, Dict[str, List[Dict]]]) -> None:
        if not self.gender_rename_map:
            return
        for categories in categorized.values():
            for cat_name, projects in categories.items():
                for p in projects:
                    rule = self.gender_rename_map.get(p["full_name"])
                    if not rule:
                        continue
                    if cat_name == "男" and rule.get("male"):
                        p["full_name"] = rule["male"]
                    elif cat_name != "男" and rule.get("female"):
                        p["full_name"] = rule["female"]

    # ---------- 转 Scheme 列表 ----------
    def _to_scheme_list(self, categorized: Dict[str, Dict[str, List[Dict]]]) -> List[Scheme]:
        schemes: List[Scheme] = []
        for sheet_name in self.sheet_names_in_order:
            if sheet_name not in categorized:
                continue
            cats = categorized[sheet_name]
            for cat in _CATEGORY_ORDER:
                projects = cats.get(cat)
                if not projects:
                    continue
                # 去重 + 按 row_index 排序
                unique = {p["full_name"]: p for p in projects}.values()
                ordered = sorted(unique, key=lambda x: x["row_index"])
                schemes.append(
                    Scheme(
                        sheet=sheet_name,
                        category=cat,
                        items=[p["full_name"] for p in ordered],
                    )
                )
        logger.info(f"Final scheme count: {len(schemes)}")
        return schemes


# ---------- 模块级工具函数 ----------
def _safe_str(value) -> str:
    """将 pandas 单元格转为去首尾空格的 str；NaN → ''"""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _update_state(text: str) -> str | None:
    """检查行文本是否命中状态触发词，返回新状态或 None"""
    for keyword, state in _STATE_TRIGGERS:
        if keyword in text:
            return state
    return None


def _normalize_item_name(name: str) -> str:
    """清洗项目名：去空格、全角括号转半角"""
    return (
        name.replace(" ", "")
        .replace("\u3000", "")
        .replace("（", "(")
        .replace("）", ")")
    )
