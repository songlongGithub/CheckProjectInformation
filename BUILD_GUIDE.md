# 打包指南

体检方案智能核对工具 - Windows & macOS 打包说明

---

## 📋 打包前准备

### 1. 环境要求

**通用要求：**
- Python 3.8 或更高版本
- pip 包管理器

**macOS 额外要求：**
- Xcode Command Line Tools（如果还没安装，运行 `xcode-select --install`）

**Windows 额外要求：**
- Microsoft Visual C++ Redistributable（通常系统已自带）

### 2. 安装依赖

在项目根目录执行：

```bash
# macOS / Linux
python3 -m pip install -r requirements.txt

# Windows
python -m pip install -r requirements.txt
```

---

## 🍎 macOS 打包

### 方式一：使用打包脚本（推荐）

1. 打开终端，进入项目目录
2. 执行打包脚本：

```bash
./build_mac.sh
```

3. 打包完成后，应用位于 `dist/体检方案智能核对工具.app`

### 方式二：手动打包

```bash
# 1. 清理旧文件
rm -rf build dist

# 2. 使用 PyInstaller 打包
python3 -m PyInstaller MedicalExamChecker.spec --clean

# 3. 应用位于 dist/体检方案智能核对工具.app
```

### macOS 安装和使用

1. 在 Finder 中打开 `dist` 文件夹
2. 将 `体检方案智能核对工具.app` 拖到「应用程序」文件夹
3. 双击运行

**注意事项：**
- 首次运行时，可能提示"无法打开，因为来自身份不明的开发者"
- 解决方法：右键点击应用 → 选择"打开" → 在弹出对话框中点击"打开"
- 或者在「系统偏好设置」→「安全性与隐私」中允许运行

---

## 🪟 Windows 打包

### 方式一：使用打包脚本（推荐）

1. 打开命令提示符（CMD）或 PowerShell
2. 进入项目目录
3. 执行打包脚本：

```cmd
build_windows.bat
```

4. 打包完成后，应用位于 `dist\体检方案智能核对工具\`

### 方式二：手动打包

```cmd
# 1. 清理旧文件
rmdir /s /q build
rmdir /s /q dist

# 2. 使用 PyInstaller 打包
python -m PyInstaller MedicalExamChecker.spec --clean

# 3. 应用位于 dist\体检方案智能核对工具\
```

### Windows 安装和使用

1. 打开 `dist\体检方案智能核对工具\` 文件夹
2. 双击 `体检方案智能核对工具.exe` 运行
3. 可以将整个文件夹复制到其他电脑使用（无需安装 Python）

**注意事项：**
- 首次运行可能被 Windows Defender 拦截
- 解决方法：点击"更多信息" → "仍要运行"

---

## 📦 打包输出说明

### macOS 输出结构

```
dist/
└── 体检方案智能核对工具.app/
    └── Contents/
        ├── MacOS/
        │   └── 体检方案智能核对工具  （可执行文件）
        ├── Resources/
        └── Info.plist
```

**文件大小：** 约 80-120 MB

### Windows 输出结构

```
dist/
└── 体检方案智能核对工具/
    ├── 体检方案智能核对工具.exe  （主程序）
    ├── Python DLLs 和依赖库
    └── 其他资源文件
```

**文件大小：** 约 100-150 MB

---

## 🔧 常见问题

### 1. 打包失败：找不到模块

**解决方法：**
```bash
pip install --upgrade pyinstaller
pip install -r requirements.txt --force-reinstall
```

### 2. macOS: 应用无法打开

**原因：** 未签名的应用被 Gatekeeper 拦截

**解决方法：**
- 方法一：右键点击 → "打开"
- 方法二：终端执行 `xattr -cr 体检方案智能核对工具.app`

### 3. Windows: 被杀毒软件拦截

**原因：** PyInstaller 打包的程序可能被误报

**解决方法：**
- 在杀毒软件中添加信任
- 或提交程序到杀毒软件厂商进行白名单申请

### 4. 打包后程序体积过大

**优化方法：**
- 使用虚拟环境打包，只安装必要的依赖
- 修改 spec 文件，排除不需要的模块

```python
# 在 MedicalExamChecker.spec 中添加
excludes=['matplotlib', 'scipy', 'numpy.tests', 'pandas.tests']
```

### 5. 打包后无法使用 OCR 功能

**原因：** 网络请求可能被防火墙拦截

**解决方法：**
- 确保允许程序访问网络
- 检查百度 OCR API 密钥配置

---

## 🚀 高级配置

### 自定义应用图标

1. 准备图标文件：
   - macOS: `.icns` 格式
   - Windows: `.ico` 格式

2. 修改 `MedicalExamChecker.spec`：

```python
# macOS
app = BUNDLE(
    ...
    icon='path/to/icon.icns',
    ...
)

# Windows
exe = EXE(
    ...
    icon='path/to/icon.ico',
    ...
)
```

### 单文件打包（仅 Windows）

将所有文件打包成一个 exe：

```bash
pyinstaller --onefile --windowed --name="体检方案智能核对工具" main.py
```

**注意：** 单文件模式启动会稍慢，但便于分发。

---

## 📝 版本信息

- **应用版本：** v2.3.0
- **Python 版本：** 3.8+
- **PyInstaller 版本：** 6.3.0
- **PyQt6 版本：** 6.6.1

---

## 📮 技术支持

如遇到打包问题，请检查：
1. Python 和 pip 版本是否符合要求
2. 所有依赖是否正确安装
3. 控制台的完整错误信息

---

**最后更新：** 2025-10-15
