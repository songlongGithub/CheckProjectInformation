# 体检方案智能核对工具

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

一个基于 PyQt6 和百度 OCR 的体检方案智能核对工具，用于自动比对 Excel 体检方案与图片内容。

</div>

## ✨ 功能特性

- 📊 **Excel 解析**：智能解析体检方案表格，自动按性别（男/女）和婚姻状态（未婚/已婚）分类
- 🔍 **OCR 识别**：集成百度 OCR API，精准识别图片中的体检项目内容
- 🎯 **智能匹配**：使用模糊匹配算法（fuzzywuzzy）自动比对 Excel 方案与 OCR 结果
- 📝 **差异报告**：生成详细的比对报告，清晰标识匹配、缺失和多余项目
- ⚙️ **规则配置**：支持自定义项目别名、重命名和性别特定规则
- 🎨 **现代界面**：基于 PyQt6 的美观现代化用户界面
- 📦 **一键打包**：支持 macOS 和 Windows 平台的独立应用打包

## 📸 应用截图

> 现代化的图形界面，操作简单直观

## 🚀 快速开始

### 环境要求

- Python 3.11 或更高版本
- macOS 或 Windows 操作系统

### 安装依赖

```bash
# 克隆项目
git clone git@github.com:songlongGithub/CheckProjectInformation.git
cd CheckProjectInformation

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖包
pip install -r requirements.txt
```

### 配置 OCR

1. 注册百度智能云账号：https://cloud.baidu.com/
2. 创建文字识别应用，获取 API Key 和 Secret Key
3. 在应用设置界面配置 API 凭据

### 运行应用

```bash
python main.py
```

## 📖 使用说明

### 基本流程

1. **加载 Excel 方案**：点击"选择Excel文件"按钮，加载体检方案表格
2. **选择图片**：点击"添加图片"按钮，选择需要核对的体检项目图片
3. **选择方案**：从解析出的方案列表中选择要核对的具体方案
4. **开始处理**：点击"开始处理"按钮，自动进行 OCR 识别和比对
5. **查看结果**：在结果区域查看详细的比对报告

### 高级配置

#### 别名规则
用于将 OCR 识别的不规范名称映射到标准名称：
```
OCR识别名 → Excel标准名
例：血糖 → 空腹血糖
```

#### 重命名规则
在解析 Excel 阶段拆分或重命名项目：
```
原始名称 → 新名称1, 新名称2
例：肝功能全套 → 谷丙转氨酶, 谷草转氨酶
```

#### 性别重命名规则
为男性和女性设置不同的项目名称：
```
原始名称 → 男性名称, 女性名称
例：泌尿系统 → 前列腺彩超, 妇科彩超
```

## 🏗️ 项目结构

```
CheckProjectInformation/
├── main.py                 # 应用入口
├── main_window.py          # 主窗口界面
├── settings_dialog.py      # 设置对话框
├── excel_parser.py         # Excel 解析器
├── logic.py                # OCR 和匹配核心逻辑
├── workers.py              # 后台线程处理
├── styles.py               # 界面样式定义
├── requirements.txt        # 项目依赖
├── MedicalExamChecker.spec # PyInstaller 配置
├── build_mac.sh            # macOS 打包脚本
├── build_windows.bat       # Windows 打包脚本
└── resources/              # 应用资源文件
    └── icons/              # 应用图标
```

## 📦 打包部署

### macOS 打包

```bash
chmod +x build_mac.sh
./build_mac.sh
```

生成的应用位于 `dist/体检方案智能核对工具.app`

### Windows 打包

```cmd
build_windows.bat
```

生成的应用位于 `dist/体检方案智能核对工具.exe`

详细打包说明请参考：
- [快速开始指南](QUICK_BUILD.md)
- [完整打包指南](BUILD_GUIDE.md)

## 🛠️ 技术栈

- **界面框架**：PyQt6 - 跨平台 GUI 框架
- **表格处理**：pandas + openpyxl - Excel 文件读取和解析
- **OCR 识别**：百度 OCR API - 文字识别服务
- **模糊匹配**：fuzzywuzzy + python-Levenshtein - 智能字符串匹配
- **HTTP 请求**：requests - API 调用
- **应用打包**：PyInstaller - 独立应用打包

## 🔧 开发指南

### Excel 格式要求

体检方案 Excel 应包含以下列：
- **项目名称**（A列）：主项目名称
- **子项目**（B列）：详细项目名称
- **内容明细**（C列）：项目描述
- **男**（D列）：是否适用于男性（√标记）
- **女**（E列）：是否适用于女性（√标记）

支持的状态标识：
- 男性检查
- 女性检查
- 女未婚检查
- 女已婚检查

### OCR 结果格式

工具会从 OCR 识别结果中提取：
1. **方案标题**：包含"方案"关键字的文本
2. **项目列表**：位于"分组价格"和"分组交费方式"之间的内容
3. 自动按顿号（、）分割项目

### 测试

```bash
# 运行 OCR 解析测试
python test_ocr_parsing.py
```

## 📝 更新日志

### v1.0.0 (2024-10-17)
- ✨ 初始版本发布
- 🎨 现代化 GUI 界面
- 🔍 百度 OCR 集成
- 📊 Excel 智能解析
- 🎯 智能匹配算法
- ⚙️ 规则配置系统
- 📦 跨平台打包支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 👨‍💻 作者

songlongGithub

## 🙏 致谢

- 感谢百度智能云提供的 OCR API 服务
- 感谢所有开源项目的贡献者

---

<div align="center">

**如果这个项目对您有帮助，请给个 ⭐️ Star 支持一下！**

</div>

