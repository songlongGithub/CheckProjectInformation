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
- 🌐 **Web 控制台**：新增 FastAPI + Vue 网页版，支持登录、规则管理、Excel/OCR 上传与比对

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

### 运行 Web 控制台

```bash
# 启动 FastAPI 后端
python -m uvicorn web_backend.app:app --reload

# 启动前端调试服务
cd web_frontend
npm install
npm run dev
```

- 预置账号：
  - `admin / jkl446041`
  - `renyanan / 931128`

> 生产环境请立刻修改密码，并仅向授权成员下发账号。

### 本地调试流程

1. **后端 / FastAPI**
   ```bash
   cd CheckProjectInformation
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   uvicorn web_backend.app:app --reload --host 0.0.0.0 --port 8001
   ```
2. **前端 / Vue 3**
   ```bash
   cd web_frontend
   npm install
   npm run dev
   ```
   默认监听 `http://localhost:5173`，通过 Vite 代理访问后端的 `http://127.0.0.1:8001`。
3. **桌面端** 如需联调 PyQt6，在激活虚拟环境后执行 `python main.py`。
4. **常见检查**
   - `python3 test_ocr_parsing.py`：快速验证 OCR 解析逻辑；
   - `curl http://127.0.0.1:8001/api/health`：确认后端存活；
   - Chrome DevTools Network 中留意 401/500 等异常响应。

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
├── web_backend/            # FastAPI Web 服务
├── web_frontend/           # Vue 3 前端项目
├── Dockerfile              # 一体化 Docker 构建文件
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

## ☁️ 云端部署

### 宝塔/腾讯云发版建议

1. **准备环境**
   ```bash
   git clone git@github.com:songlongGithub/CheckProjectInformation.git /root/projects/CheckProjectInformation
   cd /root/projects/CheckProjectInformation
   python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
   cd web_frontend && npm install && npm run build
   ```
2. **Systemd 服务**（`/etc/systemd/system/mec.service`）调用仓库根的 `run_backend.sh`，保持 uvicorn 常驻并开机自启。
3. **一键部署脚本**：服务器上执行 `bash redeploy.sh` 会自动 `git reset --hard origin/main`、重装前端依赖、`npm run build` 并 `systemctl restart mec.service`。推荐发版前先 `git pull`。
4. **Nginx/宝塔站点**：将静态目录指向 `web_frontend/dist`，再把 `/api`、`/auth` 等接口反向代理到 `http://127.0.0.1:8001`，并在安全组/宝塔防火墙放行 80/443（或需要的端口）。
5. **验证**：`systemctl status mec.service`、`curl http://127.0.0.1:8001/api/health`、浏览器访问域名/IP 确认流程可用。

### Docker 方案

使用随仓库提供的 `Dockerfile` 可以快速构建集成了 FastAPI 后端与 Vue 前端的镜像：

```bash
# 构建镜像
docker build -t medical-exam-web .

# 运行容器（暴露 8000 端口，可按需映射到 80/443）
docker run -d --name medical-exam-web -p 8000:8000 medical-exam-web
```

容器启动后访问 `http://<服务器IP>:8000/` 即可打开网页端。生产环境中建议通过宝塔配置 Nginx 反向代理，将域名和 HTTPS 证书指向该容器端口。

配置与账号信息保存在 `web_backend/web_settings.json`，也可以通过网页“系统配置”页面在线修改；若以 Docker 运行，请为该文件映射数据卷以便持久化。

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
