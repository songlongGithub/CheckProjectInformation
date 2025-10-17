#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能匹配器模块
提供基于模糊匹配和机器学习的智能项目匹配功能
减少对硬编码规则的依赖
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from fuzzywuzzy import fuzz, process

logger = logging.getLogger(__name__)


class SmartMatcher:
    """
    智能匹配器：结合规则和算法的混合匹配策略
    
    优先级：
    1. 精确匹配
    2. 规则别名匹配
    3. 智能模糊匹配
    4. 用户反馈学习
    """
    
    def __init__(self, alias_map: Dict[str, str] = None):
        """
        初始化匹配器
        
        Args:
            alias_map: 别名映射字典 {别名: 标准名}
        """
        self.alias_map = alias_map or {}
        self.match_history: List[Tuple[str, str, str]] = []  # (ocr, excel, method)
        self.learned_rules: Dict[str, str] = {}  # 从用户反馈中学习的规则
        
        # 中文医学术语的特殊处理
        self.medical_abbr = {
            'CT': '计算机断层扫描',
            'B超': '超声检查',
            'TCT': '液基薄层细胞检测',
            'HPV': '人乳头瘤病毒',
            'C13': '碳十三呼气试验',
            'C14': '碳十四呼气试验',
        }
    
    def match(self, ocr_item: str, excel_items: List[str], 
              threshold: int = 85, method: str = 'auto') -> Optional[str]:
        """
        执行智能匹配
        
        Args:
            ocr_item: OCR 识别的项目名称
            excel_items: Excel 中的标准项目列表
            threshold: 模糊匹配阈值 (0-100)
            method: 匹配方法 ('auto', 'exact', 'fuzzy', 'semantic')
        
        Returns:
            匹配到的 Excel 标准项目名，如果未匹配到返回 None
        """
        if not ocr_item or not excel_items:
            return None
        
        ocr_item = ocr_item.strip()
        
        # 1. 精确匹配
        if ocr_item in excel_items:
            self._record_match(ocr_item, ocr_item, 'exact')
            return ocr_item
        
        # 2. 规则别名匹配
        if ocr_item in self.alias_map:
            standard_name = self.alias_map[ocr_item]
            if standard_name in excel_items:
                self._record_match(ocr_item, standard_name, 'alias')
                return standard_name
        
        # 3. 学习规则匹配
        if ocr_item in self.learned_rules:
            learned_name = self.learned_rules[ocr_item]
            if learned_name in excel_items:
                self._record_match(ocr_item, learned_name, 'learned')
                return learned_name
        
        # 4. 智能模糊匹配
        if method in ['auto', 'fuzzy']:
            fuzzy_match = self._fuzzy_match(ocr_item, excel_items, threshold)
            if fuzzy_match:
                self._record_match(ocr_item, fuzzy_match, 'fuzzy')
                return fuzzy_match
        
        # 5. 语义匹配（基于规则的增强）
        if method in ['auto', 'semantic']:
            semantic_match = self._semantic_match(ocr_item, excel_items, threshold)
            if semantic_match:
                self._record_match(ocr_item, semantic_match, 'semantic')
                return semantic_match
        
        logger.debug(f"未能匹配项目: {ocr_item}")
        return None
    
    def _fuzzy_match(self, ocr_item: str, excel_items: List[str], 
                     threshold: int) -> Optional[str]:
        """
        模糊匹配策略
        使用多种评分器组合，提高匹配准确率
        """
        # 标准化处理
        normalized_ocr = self._normalize_text(ocr_item)
        normalized_items = {item: self._normalize_text(item) for item in excel_items}
        
        # 尝试多种评分策略
        scorers = [
            fuzz.ratio,           # 简单相似度
            fuzz.partial_ratio,   # 部分匹配
            fuzz.token_sort_ratio,  # 词序不敏感
            fuzz.token_set_ratio,   # 词集匹配
        ]
        
        best_match = None
        best_score = 0
        
        for scorer in scorers:
            match, score = process.extractOne(
                normalized_ocr,
                list(normalized_items.values()),
                scorer=scorer
            )
            
            if score > best_score:
                best_score = score
                # 找回原始项目名
                for original, normalized in normalized_items.items():
                    if normalized == match:
                        best_match = original
                        break
        
        if best_score >= threshold:
            logger.debug(f"模糊匹配成功: {ocr_item} -> {best_match} (得分: {best_score})")
            return best_match
        
        return None
    
    def _semantic_match(self, ocr_item: str, excel_items: List[str],
                       threshold: int) -> Optional[str]:
        """
        语义匹配：基于医学术语的特殊规则
        处理缩写、别名、部位名称等
        """
        # 扩展缩写
        expanded_ocr = self._expand_abbreviations(ocr_item)
        
        # 提取关键特征
        ocr_features = self._extract_features(expanded_ocr)
        
        # 计算语义相似度
        best_match = None
        best_score = 0
        
        for item in excel_items:
            item_features = self._extract_features(item)
            score = self._calculate_feature_similarity(ocr_features, item_features)
            
            if score > best_score:
                best_score = score
                best_match = item
        
        if best_score >= threshold:
            logger.debug(f"语义匹配成功: {ocr_item} -> {best_match} (得分: {best_score})")
            return best_match
        
        return None
    
    def _normalize_text(self, text: str) -> str:
        """文本标准化：统一格式，方便比较"""
        if not text:
            return ""
        
        # 统一括号
        text = text.replace('（', '(').replace('）', ')')
        text = text.replace('【', '[').replace('】', ']')
        
        # 移除空格
        text = text.replace(' ', '').replace('　', '')
        
        # 统一数字格式
        text = re.sub(r'[零〇]', '0', text)
        text = re.sub(r'[一壹]', '1', text)
        text = re.sub(r'[二贰]', '2', text)
        text = re.sub(r'[三叁]', '3', text)
        
        # 转小写（仅英文部分）
        return text.lower()
    
    def _expand_abbreviations(self, text: str) -> str:
        """扩展医学缩写为全称"""
        expanded = text
        for abbr, full_name in self.medical_abbr.items():
            if abbr in text:
                expanded = text.replace(abbr, full_name)
        return expanded
    
    def _extract_features(self, text: str) -> Dict[str, any]:
        """
        提取文本特征用于语义匹配
        
        特征包括：
        - 检查部位（如：肝、肾、心脏）
        - 检查方式（如：彩超、CT、X光）
        - 性别标记（如：男、女、女已婚）
        - 特殊标记（如：H、A、新）
        """
        features = {
            'parts': [],      # 身体部位
            'methods': [],    # 检查方式
            'gender': None,   # 性别
            'markers': [],    # 特殊标记
        }
        
        # 检查部位关键词
        body_parts = [
            '肝', '肾', '心', '肺', '胃', '肠', '脾', '胰',
            '甲状腺', '乳腺', '前列腺', '子宫', '卵巢',
            '头颅', '颈部', '胸部', '腹部', '盆腔',
            '血', '尿', '便', '眼', '耳', '鼻', '喉'
        ]
        
        for part in body_parts:
            if part in text:
                features['parts'].append(part)
        
        # 检查方式关键词
        methods = [
            'CT', 'MRI', 'B超', '彩超', '超声', 'X光', 'X线',
            '心电图', '脑电图', '血常规', '尿常规', '生化',
            '病理', '活检', '穿刺', '内镜', '胃镜', '肠镜'
        ]
        
        for method in methods:
            if method in text:
                features['methods'].append(method)
        
        # 性别标记
        if '女已婚' in text:
            features['gender'] = '女已婚'
        elif '女未婚' in text:
            features['gender'] = '女未婚'
        elif '女' in text:
            features['gender'] = '女'
        elif '男' in text:
            features['gender'] = '男'
        
        # 特殊标记
        markers = re.findall(r'\(([A-Z0-9]+)\)', text)
        features['markers'].extend(markers)
        
        return features
    
    def _calculate_feature_similarity(self, features1: Dict, features2: Dict) -> float:
        """计算特征相似度（0-100）"""
        score = 0
        total_weight = 0
        
        # 部位匹配权重最高
        if features1['parts'] and features2['parts']:
            part_overlap = len(set(features1['parts']) & set(features2['parts']))
            part_union = len(set(features1['parts']) | set(features2['parts']))
            if part_union > 0:
                score += (part_overlap / part_union) * 40
            total_weight += 40
        
        # 检查方式匹配
        if features1['methods'] and features2['methods']:
            method_overlap = len(set(features1['methods']) & set(features2['methods']))
            method_union = len(set(features1['methods']) | set(features2['methods']))
            if method_union > 0:
                score += (method_overlap / method_union) * 30
            total_weight += 30
        
        # 性别匹配
        if features1['gender'] or features2['gender']:
            if features1['gender'] == features2['gender']:
                score += 20
            total_weight += 20
        
        # 特殊标记匹配
        if features1['markers'] or features2['markers']:
            marker_overlap = len(set(features1['markers']) & set(features2['markers']))
            marker_union = len(set(features1['markers']) | set(features2['markers']))
            if marker_union > 0:
                score += (marker_overlap / marker_union) * 10
            total_weight += 10
        
        # 归一化到 0-100
        if total_weight > 0:
            return (score / total_weight) * 100
        return 0
    
    def _record_match(self, ocr_item: str, excel_item: str, method: str):
        """记录匹配历史，用于分析和学习"""
        self.match_history.append((ocr_item, excel_item, method))
        logger.debug(f"匹配记录: {ocr_item} -> {excel_item} (方法: {method})")
    
    def learn_from_feedback(self, ocr_item: str, correct_excel_item: str):
        """
        从用户反馈中学习
        当用户手动纠正匹配结果时，记录为新的学习规则
        """
        if ocr_item != correct_excel_item:
            self.learned_rules[ocr_item] = correct_excel_item
            logger.info(f"学习新规则: {ocr_item} -> {correct_excel_item}")
    
    def export_learned_rules(self) -> List[List[str]]:
        """
        导出学习到的规则，可以添加到正式规则库中
        
        Returns:
            规则列表，格式 [[别名, 标准名], ...]
        """
        return [[ocr, excel] for ocr, excel in self.learned_rules.items()]
    
    def get_match_statistics(self) -> Dict[str, int]:
        """获取匹配统计信息"""
        stats = {
            'total': len(self.match_history),
            'exact': 0,
            'alias': 0,
            'learned': 0,
            'fuzzy': 0,
            'semantic': 0,
        }
        
        for _, _, method in self.match_history:
            if method in stats:
                stats[method] += 1
        
        return stats
    
    def suggest_new_rules(self, min_occurrences: int = 3) -> List[Tuple[str, str, int]]:
        """
        建议新规则：频繁出现的模糊匹配可以转为固定规则
        
        Args:
            min_occurrences: 最少出现次数
        
        Returns:
            建议规则列表 [(OCR名, Excel名, 出现次数), ...]
        """
        # 统计模糊匹配和语义匹配的频率
        fuzzy_matches: Dict[Tuple[str, str], int] = {}
        
        for ocr, excel, method in self.match_history:
            if method in ['fuzzy', 'semantic']:
                key = (ocr, excel)
                fuzzy_matches[key] = fuzzy_matches.get(key, 0) + 1
        
        # 过滤出频繁出现的匹配
        suggestions = [
            (ocr, excel, count)
            for (ocr, excel), count in fuzzy_matches.items()
            if count >= min_occurrences
        ]
        
        # 按出现次数排序
        suggestions.sort(key=lambda x: x[2], reverse=True)
        
        return suggestions


# 便捷函数
def create_smart_matcher(alias_data: List[List[str]]) -> SmartMatcher:
    """
    创建智能匹配器实例
    
    Args:
        alias_data: 别名规则数据 [[别名, 标准名], ...]
    
    Returns:
        配置好的 SmartMatcher 实例
    """
    alias_map = {row[0]: row[1] for row in alias_data if len(row) >= 2}
    return SmartMatcher(alias_map)


# 使用示例
if __name__ == "__main__":
    # 示例用法
    alias_rules = [
        ['静脉采血', '采血'],
        ['碳十三呼气检查', 'C13呼气试验'],
    ]
    
    matcher = create_smart_matcher(alias_rules)
    
    # Excel 标准项目列表
    excel_items = [
        '采血',
        'C13呼气试验',
        '肝功能十三项',
        '乳腺彩色超声',
        '心电图'
    ]
    
    # 测试匹配
    test_cases = [
        '静脉采血',           # 规则匹配
        '碳13呼气检查',       # 模糊匹配
        '肝功能13项',         # 语义匹配
        '乳腺彩超',           # 语义匹配
        '心电图检查',         # 模糊匹配
    ]
    
    print("=== 智能匹配测试 ===\n")
    for ocr_item in test_cases:
        match = matcher.match(ocr_item, excel_items, threshold=80)
        if match:
            print(f"✓ {ocr_item:15s} -> {match}")
        else:
            print(f"✗ {ocr_item:15s} -> (未匹配)")
    
    print("\n=== 匹配统计 ===")
    stats = matcher.get_match_statistics()
    for method, count in stats.items():
        print(f"{method}: {count}")
    
    print("\n=== 建议新规则 ===")
    suggestions = matcher.suggest_new_rules(min_occurrences=1)
    for ocr, excel, count in suggestions:
        print(f"[{count}次] {ocr} -> {excel}")

