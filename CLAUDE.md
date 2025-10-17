# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个体检方案智能核对工具 (Medical Exam Checker)，用于自动比对 Excel 体检方案与 OCR 识别的图片内容。

**核心功能：**
- 解析 Excel 体检方案表格，按性别和婚姻状态分类
- 使用百度 OCR API 识别图片中的体检项目
- 自动匹配并对比 Excel 方案与图片内容
- 提供可视化的比对结果和差异报告

## 运行应用

```bash
# 启动 GUI 应用
python main.py
```

## 打包应用

### macOS 打包
```bash
./build_mac.sh
```

### Windows 打包
```cmd
build_windows.bat
```

详细说明：
- [快速开始](QUICK_BUILD.md)
- [完整指南](BUILD_GUIDE.md)

## 代码架构

### 核心模块关系

```
main.py (入口)
    └── MainWindow (main_window.py) - 主界面
            ├── SettingsDialog (settings_dialog.py) - 规则配置界面
            ├── MedicalExamParser (excel_parser.py) - Excel 解析
            ├── logic.py - OCR 和匹配核心逻辑
            └── Worker (workers.py) - 后台线程处理
```

### 关键处理流程

**1. Excel 解析流程 (excel_parser.py)**
- `read_excel_data()`: 读取 Excel 各 sheet
- `_clean_and_filter_projects()`: 解析项目，识别性别/婚姻状态
- `categorize_projects_by_gender_and_marital_status()`: 按 "男/女未婚/女已婚" 分类
- 支持项目重命名、拆分和性别特定重命名

**2. OCR 识别流程 (logic.py) - V2 支持多方案**
- `get_baidu_ocr_access_token()`: 获取百度 OCR token
- `get_ocr_result_from_baidu()`: 调用 OCR API
- `extract_data_from_ocr_json()`: 从 OCR JSON 提取多个方案
  - 返回: `[(方案名称, [项目列表]), ...]`
  - 识别规则:
    - **标题识别**: 包含"方案"关键字的文本（支持跨行拼接）
    - **项目范围**: "分组价格"和"分组交费方式/分组缴费方式"之间的所有文本
    - **项目拆分**: 拼接所有行后按"、"分割
  - 一张图片可识别多个方案（按顺序扫描）

**3. 匹配与对比流程 (logic.py)**
- `normalize_for_matching()`: 标准化文本（移除括号、数字、空格等）
- `find_best_match()`: 使用模糊匹配寻找最佳方案（fuzzywuzzy, 阈值 85）
- `generate_comparison_report()`: 生成逐项对比报告
  - 状态: "匹配" (完全/别名)、"缺失"、"多余"
  - 支持别名映射

**4. 状态机制 (excel_parser.py)**
- Excel 解析使用状态机跟踪当前处理的类别:
  - `NORMAL`: 通用项目
  - `MALE_ONLY`: 男性专有
  - `FEMALE_UNMARRIED`: 女未婚专有
  - `FEMALE_MARRIED`: 女已婚专有
- 状态由行标题触发切换（如"男性检查"、"女性检查"等）

### 配置存储

使用 PyQt6 的 QSettings，保存在系统配置目录:
- 组织名: "MyCompany"
- 应用名: "MedicalExamChecker"

**配置项：**
- `ocr/api_key`: 百度 OCR API Key
- `ocr/secret_key`: 百度 OCR Secret Key
- `rules/aliases`: 对比别名规则 (OCR识别名 → Excel标准名)
- `rules/renames`: 表格重命名/拆分规则 (原名 → 新名列表)
- `rules/gender_renames`: 性别特定重命名 (原名 → 男性名, 女性名)

## 依赖库

- PyQt6: GUI 框架
- pandas: Excel 解析
- requests: OCR API 调用
- fuzzywuzzy: 模糊字符串匹配
- openpyxl: Excel 文件读取

## 关键设计特点

### 别名与重命名的区别
- **重命名规则** (excel_parser.py): 在**解析 Excel 阶段**应用，改写或拆分 Excel 中的项目名
- **别名规则** (logic.py): 在**对比阶段**应用，将 OCR 识别的不规范名称映射到标准名

### 特殊项目识别
- **通用女性项目**: 乳腺彩超、盆腔彩超 - 自动分配给未婚和已婚
- **婚姻状态项目**: 包含妇科、宫颈、TCT、HPV 等关键词 - 仅分配给已婚

### 匹配优化
- 使用 `normalize_for_matching()` 移除干扰字符后再匹配
- 模糊匹配阈值设为 85，平衡准确率和召回率

## 常见任务

### 添加新的别名规则
在 `settings_dialog.py` 的 `default_aliases` 中添加 `['OCR名', 'Excel标准名']`

### 修改匹配阈值
在 `logic.py` 中修改 `find_best_match()` 的 `score >= 85` 和 `generate_comparison_report()` 的 `score >= 85`

### 调整 OCR 提取逻辑
修改 `logic.py` 的 `extract_data_from_ocr_json()` 中的标记词（当前为 "分组选项" 和 "分组信息"）
