#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
体检方案解析脚本
读取Excel体检方案，生成分类项目清单
输出格式：Markdown文件
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd

# 配置日志
def _resolve_log_file(filename: str) -> Path:
    """
    Determine a writable location for log files regardless of launch context.
    Defaults to the user's profile so Finder launches do not fail on /.
    """
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Logs" / "MedicalExamChecker"
    elif os.name == "nt":
        base_dir = Path.home() / "AppData" / "Local" / "MedicalExamChecker" / "Logs"
    else:
        base_dir = Path.home() / ".local" / "share" / "MedicalExamChecker" / "logs"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / filename


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            _resolve_log_file('medical_exam_parser.log'),
            mode='w',
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MedicalExamParser:
    """体检方案解析器"""
    
    def __init__(self, excel_file_path: str):
        self.excel_file_path = excel_file_path
        self.schemes_data: Dict[str, List[Dict]] = {}
        self.rename_map: Dict[str, List[str]] = {}
        self.gender_rename_map: Dict[str, Dict[str, str]] = {}
        self.sheet_names_in_order: List[str] = []
        self.sheet_name_alias_map: Dict[str, str] = {}

        # --- 可配置属性 ---
        self.default_to_universal_if_no_checkmark = True
        # 用于识别必须归类于“已婚”的女性项目关键词
        self.marital_status_keywords = [
            '妇科', '宫颈', 'TCT', 'HPV', '白带', '阴道', 
            '子宫', '卵巢', '宫颈刮片', '妇检'
        ]
        self.excluded_keywords = [
            '健康管理', '套餐价格', '价格', '合计', '小计', 
            '费用', '收费', '总计'
        ]
        self.package_keywords = ['全套', '套餐', '肝功十三项', '肝功十一项']
        
    def build_rename_map(self, rename_data: List[List[str]]):
        """从配置数据构建重命名映射."""
        self.rename_map.clear()
        for item in rename_data:
            if len(item) == 2 and item[0]:
                original_name, new_names_str = item
                self.rename_map[original_name] = [name.strip() for name in new_names_str.split(',')]
        logger.info(f"Built {len(self.rename_map)} rename rules from settings.")

    def build_gender_rename_map(self, gender_data: List[List[str]]):
        """从配置数据构建性别重命名映射."""
        self.gender_rename_map.clear()
        for item in gender_data:
            if len(item) == 3 and item[0]:
                original, male_name, female_name = item
                self.gender_rename_map[original] = {'male': male_name, 'female': female_name}
        logger.info(f"Built {len(self.gender_rename_map)} gender rename rules from settings.")

    def read_excel_data(self) -> None:
        """读取并解析Excel文件中的所有Sheet页."""
        try:
            logger.info(f"Reading Excel file: {self.excel_file_path}")
            xls = pd.ExcelFile(self.excel_file_path)
            raw_sheet_names = xls.sheet_names
            self.sheet_names_in_order = []
            self.sheet_name_alias_map.clear()
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
                actual_sheet_name = self.sheet_name_alias_map.get(sheet_name, sheet_name)
                logger.info(f"Processing sheet: {sheet_name}")
                df = pd.read_excel(
                    xls,
                    sheet_name=actual_sheet_name,
                    header=None,
                    usecols=[0, 1, 2, 4, 5],
                    names=['项目名称', '子项目', '内容明细', '男', '女']
                )
                projects = self._clean_and_filter_projects(df, sheet_name) or []
                self.schemes_data[sheet_name] = projects
                logger.info(f"Sheet {sheet_name} processed: {len(projects)} valid projects found")
        except Exception as e:
            logger.error(f"Error reading Excel file: {str(e)}")
            raise
            
    def _clean_and_filter_projects(self, df: pd.DataFrame, sheet_name: str) -> List[Dict]:
        """
        清理和过滤单个Sheet页的数据.
        此方法包含核心的状态机逻辑，用于识别项目所属的区块.
        """
        projects = []
        last_main_project_name = ""
        last_added_package_name = ""
        # 初始状态为通用
        current_state = 'NORMAL'
        data_started = False

        for index, row in df.iterrows():
            project_name_col_a = str(row['项目名称']).strip() if not pd.isna(row['项目名称']) else ''
            sub_project_col_b = str(row['子项目']).strip() if not pd.isna(row['子项目']) else ''
            details_col_c = str(row['内容明细']).strip() if not pd.isna(row['内容明细']) else ''

            header_text = project_name_col_a.replace(" ", "")
            if header_text == "项目或组合":
                data_started = True
                continue
            if not data_started:
                continue
            
            # 定义状态更新函数，识别区块标题
            def update_state(text: str) -> str:
                if '男性检查' in text: return 'MALE'
                if '女未婚检查' in text: return 'FEMALE_UNMARRIED'
                # '女已婚检查H' 必须在 '女已婚检查' 之前判断，以避免错误匹配
                if '女已婚检查H' in text: return 'FEMALE_MARRIED_H'
                if '女已婚检查' in text: return 'FEMALE_MARRIED'
                if '女性检查' in text: return 'FEMALE_GENERIC'
                # 标准早餐作为任何区块的结束标记
                if '标准早餐' in text: return 'NORMAL'
                return None

            # 检查整行文本以更新状态，兼容标题独占一行或与项目同在一行的情况
            full_row_text = f"{project_name_col_a} {sub_project_col_b}"
            new_state = update_state(full_row_text)
            if new_state:
                current_state = new_state
                logger.debug(f"State changed to {current_state} by text: '{full_row_text}'")

            if project_name_col_a and '健康管理' in project_name_col_a:
                logger.debug("Encountered '健康管理' section, stop processing further rows.")
                break

            # 如果当前行是纯标题行（A列有值，B/C列为空），则跳过，因为它只用于改变状态
            is_pure_header = project_name_col_a and not sub_project_col_b and not details_col_c and update_state(project_name_col_a) is not None
            if is_pure_header:
                logger.debug(f"Skipping pure header row: {project_name_col_a}")
                continue
            
            # 记录A列的主项目名称，并排除包含特定关键词的行
            if project_name_col_a: last_main_project_name = project_name_col_a
            if any(keyword in last_main_project_name for keyword in self.excluded_keywords): continue
            
            # 智能确定最终项目名称
            final_name = ""
            if any(keyword in last_main_project_name for keyword in self.package_keywords):
                if last_main_project_name != last_added_package_name:
                    final_name = last_main_project_name
                    last_added_package_name = last_main_project_name
                else: continue
            elif sub_project_col_b: final_name = sub_project_col_b
            elif project_name_col_a: final_name = project_name_col_a

            if not final_name: continue
            
            # 清洗项目名称
            final_name = final_name.replace(' ', '').replace('　', '').replace('（', '(').replace('）', ')')
            # 排除标题行自身被当作项目
            header_titles = ['男性检查', '女性检查', '女未婚检查', '女已婚检查', '女已婚检查H']
            if final_name in header_titles or any(keyword in final_name for keyword in self.excluded_keywords): continue
            
            # --- 性别归属判断逻辑 (保留) ---
            has_male_checkmark = str(row['男']).strip() == '√'
            has_female_checkmark = str(row['女']).strip() == '√'
            
            is_for_male, is_for_female = False, False
            # 1. 最高优先级：明确的 '√' 标记
            if has_male_checkmark or has_female_checkmark:
                is_for_male, is_for_female = has_male_checkmark, has_female_checkmark
            # 2. 第二优先级：上下文状态推断
            else:
                if current_state == 'MALE': is_for_male = True
                elif current_state in ['FEMALE_UNMARRIED', 'FEMALE_MARRIED', 'FEMALE_MARRIED_H', 'FEMALE_GENERIC']: is_for_female = True
                # 3. 最低优先级：默认通用规则
                elif current_state == 'NORMAL' and self.default_to_universal_if_no_checkmark: 
                    is_for_male, is_for_female = True, True

            # 基础项目信息字典，包含关键的 category_hint
            base_project = {
                'project_name': last_main_project_name, 
                'sub_project': sub_project_col_b, 
                'full_name': final_name, 
                'details': details_col_c, 
                'for_male': is_for_male, 
                'for_female': is_for_female, 
                'sheet_name': sheet_name, 
                'row_index': index + 1,  # align with actual Excel row number (1-based)
                'category_hint': current_state # 记录项目所属的区块
            }

            # 处理重命名规则
            if final_name in self.rename_map:
                new_names = self.rename_map[final_name]
                for i, new_name in enumerate(new_names):
                    if new_name == 'SELF': new_name = final_name
                    new_project = base_project.copy()
                    new_project['full_name'] = new_name
                    new_project['row_index'] += i * 0.1 # 保持排序稳定性
                    projects.append(new_project)
                continue
            
            projects.append(base_project)
        return projects
    
    def _is_universal_female_project(self, name: str) -> bool:
        """判断是否为所有女性通用的项目（例如乳腺/盆腔彩超），用于关键词豁免."""
        return (('乳腺' in name) and ('彩超' in name or '超声' in name)) or \
               (('盆腔' in name) and ('彩超' in name or '超声' in name))

    def identify_marital_status_projects(self) -> Set[str]:
        """
        预扫描所有项目，找出名称中含有婚育关键词的项目。
        此规则现在仅在处理 '女性检查' 区块时生效。
        """
        marital_set = set()
        for projects_in_sheet in self.schemes_data.values():
            for p in projects_in_sheet:
                if self._is_universal_female_project(p['full_name']): continue
                
                text_to_check = f"{p['project_name']} {p['sub_project']}"
                if any(keyword in text_to_check for keyword in self.marital_status_keywords):
                    marital_set.add(p['full_name'])
        logger.info(f"Identified {len(marital_set)} projects as marital status related by keywords for '女性检查' block.")
        return marital_set
    
    def _load_rename_map(self, file: str) -> None:
        """从文件加载通用重命名规则."""
        if not os.path.exists(file): return
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = [p.strip() for p in line.strip().split(',') if p.strip()]
                    if len(parts) >= 2 and not line.strip().startswith('#'): 
                        self.rename_map[parts[0]] = parts[1:]
        except Exception as e: 
            logger.error(f"Error reading rename file {file}: {e}")

    def _load_gender_rename_map(self, file: str) -> None:
        """从文件加载性别专属重命名规则."""
        if not os.path.exists(file): return
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = [p.strip() for p in line.strip().split(',')]
                    if len(parts) == 3 and parts[0] and not line.strip().startswith('#'):
                        self.gender_rename_map[parts[0]] = {'male': parts[1], 'female': parts[2]}
        except Exception as e: 
            logger.error(f"Error reading gender rename file {file}: {e}")

    def _apply_gender_renames(self, categorized_projects: Dict) -> None:
        """对已分类的项目应用性别专属重命名."""
        if not self.gender_rename_map: return
        for scheme, categories in categorized_projects.items():
            for cat_name, projects in categories.items():
                for project in projects:
                    rule = self.gender_rename_map.get(project['full_name'])
                    if rule:
                        if cat_name == '男' and rule.get('male'):
                            project['full_name'] = rule['male']
                        elif cat_name != '男' and rule.get('female'):
                            project['full_name'] = rule['female']

    def categorize_projects_by_gender_and_marital_status(self) -> Dict:
        """
        [最终版] 采用“组合模型”进行分类。
        一个最终方案只有在其对应的专属桶（block bucket）包含项目时才会被生成。
        """
        marital_set = self.identify_marital_status_projects()
        categorized_final: Dict[str, Dict[str, List]] = {}
        
        for s_name, projects in self.schemes_data.items():
            # 步骤1: 初始化所有中间桶
            universal_male, universal_female = [], []
            block_male, block_female_unmarried, block_female_married, block_female_married_h = [], [], [], []
            temp_block_female_generic = []

            # 步骤2: 将项目分拣到中间桶
            for p in projects:
                hint = p.get('category_hint', 'NORMAL')
                if hint == 'NORMAL':
                    if p['for_male']: universal_male.append(p.copy())
                    if p['for_female']: universal_female.append(p.copy())
                elif hint == 'MALE':
                    if p['for_male']: block_male.append(p.copy())
                elif hint == 'FEMALE_UNMARRIED':
                    if p['for_female']: block_female_unmarried.append(p.copy())
                elif hint == 'FEMALE_MARRIED':
                    if p['for_female']: block_female_married.append(p.copy())
                elif hint == 'FEMALE_MARRIED_H':
                    if p['for_female']: block_female_married_h.append(p.copy())
                elif hint == 'FEMALE_GENERIC':
                    if p['for_female']: temp_block_female_generic.append(p.copy())

            # 步骤3: 特殊处理“女性检查”桶
            if temp_block_female_generic:
                logger.info(f"Processing '女性检查' block for sheet '{s_name}'...")
                # 规则: 默认都给已婚
                block_female_married.extend([item.copy() for item in temp_block_female_generic])
                # 规则: 过滤婚育项后，给未婚
                non_marital_items = [p for p in temp_block_female_generic if p['full_name'] not in marital_set]
                block_female_unmarried.extend([item.copy() for item in non_marital_items])
            
            # 步骤4: 根据最终规则组合并生成方案
            categorized_final[s_name] = {}
            
            # [最终逻辑] 仅当专属桶(block_...)有内容时，才生成对应的最终方案
            if block_male:
                categorized_final[s_name]['男'] = universal_male + block_male
            if block_female_unmarried:
                categorized_final[s_name]['女未婚'] = universal_female + block_female_unmarried
            if block_female_married:
                categorized_final[s_name]['女已婚'] = universal_female + block_female_married
            if block_female_married_h:
                categorized_final[s_name]['女已婚检查H'] = universal_female + block_female_married_h
                
        logger.info("Categorization completed using the final 'Combination Model'.")
        return categorized_final
    
    def _format_scheme_title(self, base_name: str, category: str) -> str:
        """格式化输出的Markdown标题."""
        base_name = re.sub(r'(男|女|女未婚|女已婚|女已婚检查H)$', '', base_name).strip()
        
        match = re.search(r'([（\(].*[）\)])', base_name)
        if match:
            paren_part = match.group(1)
            base_part = base_name.replace(paren_part, '').strip()
            return f"{base_part}{category}{paren_part}"
        else:
            return f"{base_name}{category}"

    def generate_markdown_output(self, categorized_projects: Dict, file: str) -> None:
        """生成最终的Markdown文件."""
        category_order = ['男', '女未婚', '女已婚', '女已婚检查H']

        with open(file, 'w', encoding='utf-8') as f:
            f.write("# 体检方案项目清单\n\n")
            for s_name in self.sheet_names_in_order:
                if s_name not in categorized_projects: continue
                cats = categorized_projects[s_name]
                if not cats: continue # 如果此方案下没有任何分类生成，则跳过
                
                f.write(f'---\n\n# 方案: {s_name}\n\n')
                
                for cat_name in category_order:
                    projects = cats.get(cat_name)
                    if not projects: continue
                    
                    # 按原始行号排序并去重
                    unique_projects = sorted(
                        list({p['full_name']: p for p in projects}.values()), 
                        key=lambda x: x['row_index']
                    )
                    
                    new_title = self._format_scheme_title(s_name, cat_name)
                    f.write(f"## {new_title} ({len(unique_projects)}项)\n\n")
                    for i, p in enumerate(unique_projects, 1):
                        f.write(f"{i}. {p['full_name']}\n")
                    f.write("\n")
        logger.info(f"Markdown output successfully generated at: {file}")

    def process(self, out_file: str, rename_file: str = None, gender_rename_file: str = None) -> None:
        """执行完整的处理流程."""
        try:
            if rename_file: self._load_rename_map(rename_file)
            if gender_rename_file: self._load_gender_rename_map(gender_rename_file)
            
            self.read_excel_data()
            categorized = self.categorize_projects_by_gender_and_marital_status()
            self._apply_gender_renames(categorized)
            self.generate_markdown_output(categorized, out_file)
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description="解析体检方案Excel文件")
    parser.add_argument("input_file", type=str, help="输入的Excel文件名")
    parser.add_argument("-o", "--output", type=str, default=None, help="输出的Markdown文件名")
    parser.add_argument("-r", "--rename", type=str, default=None, help="通用重命名规则文件名")
    parser.add_argument("--gender-rename", type=str, default=None, help="性别专属重命名规则文件名")
    args = parser.parse_args()
    
    out_file = args.output or f"{os.path.splitext(args.input_file)[0]}.md"
    
    if not os.path.exists(args.input_file):
        logger.critical(f"Error: Input file not found '{args.input_file}'")
        return
        
    try:
        parser_instance = MedicalExamParser(args.input_file)
        parser_instance.process(out_file, rename_file=args.rename, gender_rename_file=args.gender_rename)
    except Exception as e:
        logger.critical(f"Main process failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
