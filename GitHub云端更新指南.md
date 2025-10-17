# GitHub 云端更新配置指南

## 📋 配置概览

您的项目已配置使用 GitHub 作为规则库云端服务器：

- **仓库地址**: `https://github.com/songlongGithub/CheckProjectInformation`
- **规则文件**: `default_rules.json`
- **更新地址**: `https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json`

---

## ✅ 已完成的配置

### 1. settings_dialog.py 已更新

```python
# 第 403 行
online_url = "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json"
```

✅ 已配置为使用您的 GitHub 仓库

---

## 🚀 使用流程

### 工作原理

```
1. 用户点击"在线更新"按钮
         ↓
2. 从 GitHub 下载 default_rules.json 的最新版本
         ↓
3. 比较版本号（本地 vs GitHub）
         ↓
4. 如果 GitHub 版本更新，自动下载并保存
         ↓
5. 刷新规则，立即生效
```

---

## 📝 发布新版本规则

### 方法一：通过 Git 命令（推荐）

#### 步骤 1: 更新规则文件

编辑 `default_rules.json`，修改版本号和规则内容：

```json
{
  "version": "1.1.0",  // 更新版本号
  "last_updated": "2025-10-18",
  "changelog": "新增 10 条体检项目别名",  // 添加更新说明
  "aliases": [
    ["新项目OCR名", "新项目标准名"],  // 添加新规则
    // ... 其他规则
  ]
}
```

#### 步骤 2: 提交并推送

```bash
cd /Users/shtexaisonglong/Documents/python/checkProjectInformation

# 1. 查看修改
git status

# 2. 添加规则文件
git add default_rules.json

# 3. 提交更改
git commit -m "chore: 更新规则库到 v1.1.0 - 新增 10 条别名规则"

# 4. 推送到 GitHub
git push origin main
```

#### 步骤 3: 验证发布

```bash
# 访问 GitHub Raw URL 查看最新内容
curl https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json

# 或在浏览器中打开
open https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json
```

---

### 方法二：通过 GitHub 网页（简单快捷）

#### 步骤 1: 打开 GitHub 仓库

```
https://github.com/songlongGithub/CheckProjectInformation
```

#### 步骤 2: 找到并编辑文件

1. 点击 `default_rules.json` 文件
2. 点击右上角的 ✏️ 编辑按钮（Edit this file）
3. 直接在网页上修改规则内容
4. **重要**：更新 `version` 字段

#### 步骤 3: 提交更改

1. 页面底部填写提交信息：
   - **Commit message**: `更新规则库到 v1.1.0`
   - **Extended description**: `新增 10 条体检项目别名规则`
2. 选择 "Commit directly to the main branch"
3. 点击 "Commit changes"

#### 步骤 4: 等待生效

GitHub 需要几秒到几分钟时间更新 Raw 文件缓存。

---

## 🧪 测试更新功能

### 测试步骤

#### 1. 准备测试环境

```bash
# 备份当前规则
cp default_rules.json default_rules.backup.json

# 模拟旧版本（修改本地版本号）
# 在 default_rules.json 中将 version 改为 "1.0.0"
```

#### 2. 确保 GitHub 有新版本

确认 GitHub 上的 `default_rules.json` 版本号 > 本地版本号。

#### 3. 测试更新

```bash
# 启动应用
python3 main.py

# 操作流程:
# 1. 点击"设置"按钮
# 2. 点击"🔄 在线更新规则"按钮
# 3. 点击"是"确认更新
# 4. 等待下载完成
# 5. 查看更新结果
```

#### 4. 验证结果

```bash
# 方法1: 查看版本号
cat default_rules.json | grep version

# 方法2: 在 GUI 中查看规则表格是否更新
```

---

## 📊 版本管理策略

### 语义化版本规范

```
主版本.次版本.修订版
MAJOR.MINOR.PATCH

1.0.0  初始发布
  ↓
1.0.1  修复别名错误（Bug 修复）
  ↓
1.1.0  新增 20 条规则（新功能）
  ↓
1.2.0  新增重命名规则（新功能）
  ↓
2.0.0  重构规则格式（不兼容变更）
```

### 版本号递增规则

- **修订版 +1**: 修复现有规则的错误
- **次版本 +1**: 添加新规则（向后兼容）
- **主版本 +1**: 规则格式变更（可能不兼容）

### 发布检查清单

发布新版本前，请确认：

- [ ] 更新了 `version` 字段
- [ ] 更新了 `last_updated` 字段
- [ ] 添加了 `changelog` 说明（可选）
- [ ] JSON 格式正确（可用在线工具验证）
- [ ] 测试过规则的有效性
- [ ] 提交信息清晰明确

---

## 🌐 GitHub Raw URL 说明

### URL 格式

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/<分支名>/<文件路径>
```

### 您的项目

```
用户名: songlongGithub
仓库名: CheckProjectInformation
分支名: main
文件路径: default_rules.json

完整 URL:
https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json
```

### 访问测试

```bash
# 命令行测试
curl -i https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json

# 查看 HTTP 头（检查缓存）
curl -I https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json

# Python 测试
python3 -c "
import requests
r = requests.get('https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json')
print('状态码:', r.status_code)
print('版本号:', r.json()['version'])
"
```

---

## 🔒 访问权限

### 公开仓库（当前配置）✅

- ✅ 无需认证即可访问
- ✅ 所有用户都可以在线更新
- ✅ 适合公开分发的应用

### 私有仓库

如果您的仓库是私有的，需要额外配置：

#### 方法 1: 使用 Personal Access Token

```python
# 在 rule_manager.py 中修改请求
headers = {
    'Authorization': 'token YOUR_GITHUB_TOKEN'
}
response = requests.get(url, headers=headers, timeout=10)
```

#### 方法 2: 使用 GitHub Release

```python
# 使用 GitHub Release API
url = "https://api.github.com/repos/songlongGithub/CheckProjectInformation/releases/latest"
```

---

## 📦 高级配置

### 多版本支持

在 GitHub 上维护多个版本：

```
main 分支            - 最新稳定版 (v1.2.0)
develop 分支         - 开发版 (v1.3.0-beta)
release/v1.1 分支    - 旧版本维护 (v1.1.5)
```

用户可以选择更新源：

```python
# 稳定版
online_url = "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json"

# 开发版
online_url = "https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/develop/default_rules.json"
```

---

### 使用 GitHub Release

更专业的发布方式：

#### 创建 Release

```bash
# 1. 创建 tag
git tag -a v1.1.0 -m "规则库 v1.1.0"
git push origin v1.1.0

# 2. 在 GitHub 网页上创建 Release
# 访问: https://github.com/songlongGithub/CheckProjectInformation/releases/new
# 上传 default_rules.json 作为附件
```

#### 修改代码使用 Release API

```python
# 获取最新 Release
api_url = "https://api.github.com/repos/songlongGithub/CheckProjectInformation/releases/latest"
response = requests.get(api_url)
latest_release = response.json()

# 下载附件
for asset in latest_release['assets']:
    if asset['name'] == 'default_rules.json':
        download_url = asset['browser_download_url']
        # 下载并保存...
```

---

## 🔄 缓存处理

### GitHub Raw 文件缓存

GitHub 会缓存 Raw 文件约 5 分钟。

#### 强制刷新缓存

```bash
# 方法1: 添加随机参数
https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json?t=1234567890

# 方法2: 使用 jsdelivr CDN（自动刷新）
https://cdn.jsdelivr.net/gh/songlongGithub/CheckProjectInformation@main/default_rules.json
```

#### 在代码中处理

```python
import time

# 添加时间戳参数绕过缓存
timestamp = int(time.time())
url = f"{base_url}?t={timestamp}"
```

---

## 🐛 故障排查

### 问题 1: 404 Not Found

**可能原因：**
- 仓库是私有的
- 文件路径错误
- 分支名称错误

**解决方法：**
```bash
# 检查文件是否存在
ls -la default_rules.json

# 检查当前分支
git branch --show-current

# 在浏览器中访问 URL 查看详细错误
```

---

### 问题 2: 更新后仍是旧版本

**可能原因：**
- GitHub 缓存未刷新
- 推送未完成

**解决方法：**
```bash
# 1. 确认 GitHub 上的版本
curl https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json | grep version

# 2. 等待 5 分钟后重试

# 3. 使用 CDN URL（无缓存）
https://cdn.jsdelivr.net/gh/songlongGithub/CheckProjectInformation@main/default_rules.json
```

---

### 问题 3: 国内访问 GitHub 慢

**解决方法：**

#### 方案 A: 使用 Gitee 镜像

```bash
# 1. 在 Gitee 创建仓库镜像
# 访问: https://gitee.com/projects/import/url

# 2. 配置自动同步

# 3. 修改 URL
online_url = "https://gitee.com/songlongGithub/CheckProjectInformation/raw/main/default_rules.json"
```

#### 方案 B: 使用 jsDelivr CDN

```python
# 修改 settings_dialog.py
online_url = "https://cdn.jsdelivr.net/gh/songlongGithub/CheckProjectInformation@main/default_rules.json"

# 优点:
# - 全球 CDN 加速
# - 国内访问快
# - 自动更新（24小时缓存）
```

---

## 📊 监控和分析

### 查看下载统计

GitHub 不直接提供 Raw 文件下载统计，但可以：

#### 使用 GitHub Traffic

```
访问: https://github.com/songlongGithub/CheckProjectInformation/graphs/traffic
```

查看：
- 访问量（Views）
- 克隆量（Clones）
- 热门文件

#### 添加自定义统计

```python
# 在下载时发送统计信息
import requests

def update_rules_online_with_stats(self, url):
    # 下载规则
    response = requests.get(url)
    
    # 发送统计（可选）
    stats_url = "https://your-analytics-server.com/track"
    requests.post(stats_url, json={
        'event': 'rule_update',
        'version': response.json()['version'],
        'timestamp': datetime.now().isoformat()
    })
```

---

## ✅ 完整示例

### 发布新版本完整流程

```bash
# === 步骤 1: 编辑规则文件 ===
vi default_rules.json
# 修改内容:
# - version: "1.0.0" → "1.1.0"
# - last_updated: 更新日期
# - 添加新的别名规则

# === 步骤 2: 验证 JSON 格式 ===
python3 -m json.tool default_rules.json > /dev/null
echo "JSON 格式检查: $?"

# === 步骤 3: 提交到 Git ===
git add default_rules.json
git commit -m "feat: 更新规则库到 v1.1.0

- 新增 15 条体检项目别名
- 修复 3 条错误的映射
- 优化重命名规则"

# === 步骤 4: 推送到 GitHub ===
git push origin main

# === 步骤 5: 等待生效 ===
sleep 60  # 等待 1 分钟

# === 步骤 6: 验证发布 ===
curl -s https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json | grep version

# === 步骤 7: 测试更新功能 ===
python3 -c "
from rule_manager import get_rule_manager
rule_mgr = get_rule_manager()
url = 'https://raw.githubusercontent.com/songlongGithub/CheckProjectInformation/main/default_rules.json'
success = rule_mgr.update_rules_online(url)
print('更新成功!' if success else '已是最新版本')
print(f'当前版本: {rule_mgr.version}')
"
```

---

## 🎓 最佳实践

### 1. 版本命名规范

```bash
# 推荐的提交信息格式
git commit -m "feat: 更新规则库到 v1.1.0 - 新增体检项目别名"
git commit -m "fix: 修复肝功能项目映射错误 (v1.0.1)"
git commit -m "docs: 更新规则说明文档"
```

### 2. 定期维护

```bash
# 每月检查一次
# 1. 收集用户反馈的新项目
# 2. 整理成规则更新
# 3. 测试验证
# 4. 发布新版本
```

### 3. 回滚方案

```bash
# 如果新版本有问题，快速回滚
git revert HEAD
git push origin main

# 或回滚到特定版本
git checkout <commit-hash> -- default_rules.json
git commit -m "revert: 回滚规则库到 v1.0.0"
git push origin main
```

---

## 📚 相关资源

### 文档

- [在线更新功能详解.md](在线更新功能详解.md) - 代码实现详解
- [在线更新测试指南.md](在线更新测试指南.md) - 测试方法
- [RULE_MANAGEMENT.md](RULE_MANAGEMENT.md) - 规则管理指南

### 工具

- **JSON 验证**: https://jsonlint.com/
- **GitHub Raw URL 生成器**: https://raw.githack.com/
- **CDN 加速**: https://www.jsdelivr.com/

### GitHub 文档

- [About GitHub Raw](https://docs.github.com/en/repositories/working-with-files/using-files/viewing-a-file)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)

---

## 🎉 总结

您的项目现已配置为使用 GitHub 作为云端规则库服务器：

✅ **自动化**: 推送到 GitHub → 用户自动更新  
✅ **版本管理**: Git 自动跟踪所有历史版本  
✅ **团队协作**: 多人可协作维护规则库  
✅ **免费稳定**: GitHub 提供免费可靠的托管  
✅ **全球加速**: 可使用 CDN 加速访问  

**下一步：**
1. 测试从 GitHub 更新功能
2. 发布第一个新版本规则
3. 收集用户反馈持续改进

有任何问题随时反馈！🎊

