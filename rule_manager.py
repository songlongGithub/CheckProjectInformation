#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则管理器模块
负责加载、更新和管理体检项目的别名/重命名规则
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class RuleManager:
    """规则管理器：支持本地规则文件和在线更新"""
    
    def __init__(self, local_rules_file: str = "default_rules.json"):
        self.local_rules_file = Path(local_rules_file)
        self.rules_data: Dict = {}
        self.version = "1.0.0"
        
    def load_rules(self) -> Tuple[List[List[str]], List[List[str]], List[List[str]]]:
        """
        加载规则文件，返回 (aliases, renames, gender_renames)
        优先级：本地文件 > 内置默认规则
        """
        # 尝试从文件加载
        if self.local_rules_file.exists():
            try:
                with open(self.local_rules_file, 'r', encoding='utf-8') as f:
                    self.rules_data = json.load(f)
                    self.version = self.rules_data.get("version", "1.0.0")
                    logger.info(f"已从 {self.local_rules_file} 加载规则，版本：{self.version}")
                    
                    return (
                        self.rules_data.get("aliases", []),
                        self.rules_data.get("renames", []),
                        self.rules_data.get("gender_renames", [])
                    )
            except Exception as e:
                logger.error(f"加载规则文件失败: {e}，使用内置默认规则")
        
        # 使用内置默认规则（兜底）
        return self._get_builtin_rules()
    
    def _get_builtin_rules(self) -> Tuple[List[List[str]], List[List[str]], List[List[str]]]:
        """内置默认规则（作为兜底方案）"""
        default_aliases = [
            ['静脉采血', '采血'],
            ['眼科常规', '眼科检查'],
            ['营养B餐', '标准早餐'],
            # 这里只保留少量核心规则作为兜底
        ]
        default_renames = [
            ['一般检查', '身高体重,血压,放射项目不出胶片,超声项目不出片'],
        ]
        default_gender_renames = [
            ['外科检查', '外科检查（男）', '外科检查（女）']
        ]
        return default_aliases, default_renames, default_gender_renames
    
    def save_rules(self, aliases: List[List[str]], renames: List[List[str]], 
                   gender_renames: List[List[str]]) -> bool:
        """保存规则到本地文件"""
        try:
            self.rules_data = {
                "version": self.version,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "aliases": aliases,
                "renames": renames,
                "gender_renames": gender_renames
            }
            
            with open(self.local_rules_file, 'w', encoding='utf-8') as f:
                json.dump(self.rules_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"规则已保存到 {self.local_rules_file}")
            return True
        except Exception as e:
            logger.error(f"保存规则文件失败: {e}")
            return False
    
    def export_rules_to_csv(self, output_dir: str = ".") -> bool:
        """导出规则为 CSV 格式（方便用户编辑）"""
        try:
            import csv
            output_path = Path(output_dir)
            
            # 导出别名规则
            with open(output_path / "aliases.csv", 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['别名(OCR识别名)', '标准名(Excel标准名)'])
                writer.writerows(self.rules_data.get("aliases", []))
            
            # 导出重命名规则
            with open(output_path / "renames.csv", 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['原项目名', '新项目名(多个用英文逗号分隔)'])
                writer.writerows(self.rules_data.get("renames", []))
            
            # 导出性别规则
            with open(output_path / "gender_renames.csv", 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['原项目名', '男性新名', '女性新名'])
                writer.writerows(self.rules_data.get("gender_renames", []))
            
            logger.info(f"规则已导出为 CSV 文件到 {output_path}")
            return True
        except Exception as e:
            logger.error(f"导出 CSV 失败: {e}")
            return False
    
    def import_rules_from_csv(self, csv_dir: str = ".") -> bool:
        """从 CSV 文件导入规则"""
        try:
            import csv
            csv_path = Path(csv_dir)
            
            aliases, renames, gender_renames = [], [], []
            
            # 导入别名规则
            if (csv_path / "aliases.csv").exists():
                with open(csv_path / "aliases.csv", 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    next(reader)  # 跳过表头
                    aliases = [row for row in reader if len(row) >= 2]
            
            # 导入重命名规则
            if (csv_path / "renames.csv").exists():
                with open(csv_path / "renames.csv", 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    next(reader)
                    renames = [row for row in reader if len(row) >= 2]
            
            # 导入性别规则
            if (csv_path / "gender_renames.csv").exists():
                with open(csv_path / "gender_renames.csv", 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    next(reader)
                    gender_renames = [row for row in reader if len(row) >= 3]
            
            # 保存到 JSON 文件
            return self.save_rules(aliases, renames, gender_renames)
            
        except Exception as e:
            logger.error(f"从 CSV 导入失败: {e}")
            return False
    
    def update_rules_online(self, url: str) -> bool:
        """
        从在线源更新规则（预留接口）
        可以连接到一个中央规则库，定期获取最新的医疗项目别名
        """
        try:
            import requests
            
            # 重新读取本地版本（避免使用缓存的版本号）
            if self.local_rules_file.exists():
                try:
                    with open(self.local_rules_file, 'r', encoding='utf-8') as f:
                        local_data = json.load(f)
                        self.version = local_data.get("version", "1.0.0")
                except:
                    pass
            
            logger.info(f"正在从云端获取规则: {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            logger.info(f"云端规则获取成功，响应大小: {len(response.content)} 字节")
            
            online_rules = response.json()
            
            # 打印云端规则信息
            online_version = online_rules.get("version", "0.0.0")
            online_updated = online_rules.get("last_updated", "未知")
            aliases_count = len(online_rules.get("aliases", []))
            renames_count = len(online_rules.get("renames", []))
            gender_renames_count = len(online_rules.get("gender_renames", []))
            
            logger.info(f"云端规则信息 - 版本: {online_version}, 更新时间: {online_updated}")
            logger.info(f"云端规则统计 - 别名: {aliases_count}条, 重命名: {renames_count}条, 性别重命名: {gender_renames_count}条")
            logger.info(f"本地当前版本: {self.version}")
            
            # 检查版本号，只有更新的版本才覆盖
            if self._compare_version(online_version, self.version) > 0:
                logger.info(f"云端版本 {online_version} 高于本地版本 {self.version}，开始更新...")
                
                with open(self.local_rules_file, 'w', encoding='utf-8') as f:
                    json.dump(online_rules, f, ensure_ascii=False, indent=2)
                
                self.rules_data = online_rules
                self.version = online_version
                logger.info(f"✅ 规则已成功更新到版本 {online_version}")
                return True
            else:
                logger.info(f"当前本地版本 {self.version} 已是最新，无需更新")
                return False
                
        except Exception as e:
            logger.error(f"在线更新规则失败: {e}")
            return False
    
    def _compare_version(self, v1: str, v2: str) -> int:
        """比较版本号，返回 1/-1/0"""
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            for i in range(max(len(v1_parts), len(v2_parts))):
                p1 = v1_parts[i] if i < len(v1_parts) else 0
                p2 = v2_parts[i] if i < len(v2_parts) else 0
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except:
            return 0
    
    def add_user_rule(self, rule_type: str, rule_data: List[str]) -> bool:
        """
        添加用户自定义规则
        rule_type: 'alias', 'rename', 'gender_rename'
        """
        try:
            if rule_type == 'alias' and len(rule_data) >= 2:
                self.rules_data.setdefault("aliases", []).append(rule_data[:2])
            elif rule_type == 'rename' and len(rule_data) >= 2:
                self.rules_data.setdefault("renames", []).append(rule_data[:2])
            elif rule_type == 'gender_rename' and len(rule_data) >= 3:
                self.rules_data.setdefault("gender_renames", []).append(rule_data[:3])
            else:
                return False
            
            # 保存到文件
            return self.save_rules(
                self.rules_data.get("aliases", []),
                self.rules_data.get("renames", []),
                self.rules_data.get("gender_renames", [])
            )
        except Exception as e:
            logger.error(f"添加用户规则失败: {e}")
            return False


# 单例模式
_rule_manager_instance: Optional[RuleManager] = None

def get_rule_manager(local_rules_file: str = "default_rules.json") -> RuleManager:
    """获取规则管理器单例"""
    global _rule_manager_instance
    if _rule_manager_instance is None:
        _rule_manager_instance = RuleManager(local_rules_file)
    return _rule_manager_instance

