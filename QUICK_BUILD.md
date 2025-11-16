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

---

## Web 版部署（FastAPI + Vue）

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   cd web_frontend && npm install && npm run build
   ```

2. **启动后端**
   ```bash
   uvicorn web_backend.app:app --host 0.0.0.0 --port 8000
   ```

3. **访问网页**
   打开浏览器访问 `http://服务器IP:8000`，默认账号为 `admin / ChangeMe123!`，登录后请立即修改。

### Docker 方式（推荐用于腾讯云宝塔 Linux）

```bash
docker build -t medical-exam-web .
docker run -d --name medical-exam-web -p 8000:8000 \
  -v /opt/medical_exam_data/web_settings.json:/app/web_backend/web_settings.json \
  medical-exam-web
```

> 在宝塔面板中可直接使用“Docker 管理器”构建并运行镜像，或通过 `docker compose` 持续化部署；随后使用宝塔的 Nginx 站点将域名转发到容器 8000 端口，并开启 HTTPS。

### 配置提示

- OCR Key／Secret、规则、账号配置均可在网页的“系统配置”中修改，存储于 `web_backend/web_settings.json`。
- Excel/OCR 上传文件只在内存中保留当前会话，不会写入磁盘，可满足“会话结束即清除”的要求。
