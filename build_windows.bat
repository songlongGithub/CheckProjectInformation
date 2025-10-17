@echo off
REM Windows 打包脚本
chcp 65001 >nul

echo =========================================
echo 体检方案智能核对工具 - Windows 打包脚本
echo =========================================

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3
    pause
    exit /b 1
)

echo 1. 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo 2. 检查并安装依赖...
python -m pip install -r requirements.txt

if not exist resources\icons\MedicalExamChecker.ico (
    echo 错误: 未找到应用图标 resources\icons\MedicalExamChecker.ico，请确认已生成图标文件。
    pause
    exit /b 1
)

echo 3. 使用 PyInstaller 打包应用...
python -m PyInstaller MedicalExamChecker.spec --clean

if %errorlevel% equ 0 (
    echo.
    echo =========================================
    echo ✅ 打包完成！
    echo =========================================
    echo 应用位置: dist\体检方案智能核对工具\
    echo.
    echo 使用说明:
    echo 1. 打开 dist\体检方案智能核对工具\ 文件夹
    echo 2. 双击运行 "体检方案智能核对工具.exe"
    echo 3. 可以将整个文件夹复制到其他电脑使用
    echo =========================================
) else (
    echo.
    echo ❌ 打包失败，请检查错误信息
    pause
    exit /b 1
)

pause
