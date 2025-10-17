# 快速打包指南

## macOS 打包（3步）

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 执行打包脚本
./build_mac.sh

# 3. 查看结果
open dist
```

打包完成的应用：`dist/体检方案智能核对工具.app`

---

## Windows 打包（3步）

```cmd
# 1. 安装依赖
pip install -r requirements.txt

# 2. 执行打包脚本
build_windows.bat

# 3. 查看结果（资源管理器打开 dist 文件夹）
explorer dist
```

打包完成的应用：`dist\体检方案智能核对工具\体检方案智能核对工具.exe`

---

## 注意事项

✅ **macOS：** 首次运行右键点击应用选择"打开"
✅ **Windows：** 首次运行可能需要点击"更多信息" → "仍要运行"
✅ **分发：** 可直接复制 dist 文件夹内容到其他电脑使用

详细说明请参考 [BUILD_GUIDE.md](BUILD_GUIDE.md)
