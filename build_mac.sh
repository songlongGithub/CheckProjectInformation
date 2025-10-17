#!/bin/bash
# macOS 打包脚本

echo "========================================="
echo "体检方案智能核对工具 - macOS 打包脚本"
echo "========================================="

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

echo "1. 清理旧的构建文件..."
rm -rf build dist

echo "2. 检查并安装依赖..."
python3 -m pip install -r requirements.txt

ICON_PATH="resources/icons/MedicalExamChecker.icns"
if [ ! -f "$ICON_PATH" ]; then
    echo "错误: 未找到应用图标 $ICON_PATH，请确认已生成图标文件。"
    exit 1
fi

echo "3. 使用 PyInstaller 打包应用..."
python3 -m PyInstaller MedicalExamChecker.spec --clean

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "✅ 打包完成！"
    echo "========================================="
    echo "应用位置: dist/体检方案智能核对工具.app"
    echo ""
    echo "使用说明:"
    echo "1. 在 Finder 中打开 dist 文件夹"
    echo "2. 将 '体检方案智能核对工具.app' 拖到应用程序文件夹"
    echo "3. 双击运行"
    echo ""
    echo "注意: 首次运行可能需要在系统偏好设置中允许运行"
    echo "========================================="
else
    echo ""
    echo "❌ 打包失败，请检查错误信息"
    exit 1
fi
