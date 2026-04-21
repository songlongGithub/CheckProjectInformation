# 新架构端到端验证报告

**生成时间**：2026-04-20
**验证范围**：composites 重构 + 三层匹配 + LLM 抽象 + 降级路径

---

## 一、核心回归（沙盒内已验证）

| 指标 | 旧值 | 新值 | 说明 |
|---|---|---|---|
| test/2 女已婚 Excel 项数 | 33 | **32** | `SELF,白带常规` 膨胀已消除 |
| Excel 是否含"白带常规" | 是 | **否** | 只保留业务源字段"妇科检查" |
| "白带常规 false-missing" | 经常触发 | **不再触发** | 根因消除 |
| rules 配置 | renames 污染 | composites 字段 | 业务语义单一入口 |

## 二、三层匹配 + 降级矩阵

| 层级 | 匹配器 | match_type | 通过 |
|---|---|---|---|
| L1 | 别名归一 + 字符相等 | `exact` / `alias` | ✅ |
| L2 | fuzzywuzzy ≥ 85 | `fuzzy` | ✅ |
| L3 | Gemini/Claude 语义（默认 ON，可 --no-llm） | `llm` | ✅（抽象层构造 OK，实调需外网） |
| L4 | composites 父项覆盖 | `composite` | ✅ |
| L5 | 剩余项判缺失/多余 | — | ✅ |
| 降级 | llm_client=None 时静默跳过 L3 | — | ✅ |

## 三、composites 典型验证

```
Excel：['妇科检查', '白带常规', '血压']
OCR  ：['妇科检查', '血压']
输出 ：
  [匹配] 妇科检查 ↔ 妇科检查   type=exact
  [匹配] 血压    ↔ 血压      type=exact
  [匹配] 白带常规 ↔ ∈妇科检查  type=composite  reason=父项'妇科检查'覆盖
```

## 四、沙盒验证结果摘要

```
【回归验证】A1 重构后 Excel 女已婚 = 32 项（前值=33，现=32，消除 1 项膨胀）
  白带常规 是否仍在 Excel 里？ False（应为 False）
  妇科检查 在 Excel 里？ True（应为 True）

【场景A】OCR 识到"妇科检查"同构 Excel 项目 → 缺失 0，多余 0
【场景B】llm_client=None 降级：OK
【场景C】composites 父项覆盖：白带常规 type=composite 通过
【场景D】LLM 客户端构造：GeminiClient OK
```

## 五、Gemini 真实调用验证（在本机跑）

沙盒无外网。请在 Mac 上执行以下任一方式：

### 方式 A：双击一键脚本
```
在 Finder 中双击：run_verify.command
```
脚本会自动：
- 检测 `GEMINI_API_KEY` 环境变量 或 `skills/medical-exam-checker/config/credentials.json` 中的 gemini.api_key
- 对 `test/1..4` 全量跑 OCR + 三层匹配 + 报告生成
- 输出到 `test/<N>/report.json` 与 `test/<N>/report.md`
- 无 Gemini key 时自动降级为 `--no-llm`（规则 + fuzzy）

### 方式 B：命令行
```bash
cd /path/to/CheckProjectInformation
export GEMINI_API_KEY="..."   # 或写进 config/credentials.json
./run_verify.command
```

### 如何检查 Gemini 实际被触发
运行完成后查看任一 `test/<N>/report.md`，搜索 `（语义）` 字样即为 LLM 层命中；或查看 `.llm_cache/` 目录是否生成 JSON 缓存文件（每次真实调用都会写缓存）。

---

## 六、交付清单

- `run_verify.command` —— 双击一键验证
- `skills/medical-exam-checker/` —— 新架构完整产物
  - `scripts/core/matcher.py` —— 三层匹配
  - `scripts/core/llm_client.py` —— Gemini/Claude 抽象
  - `scripts/core/rules.py` —— composites 加载
  - `config/default_rules.json` —— 已迁移到 composites
  - `config/credentials.example.json` —— 三家密钥模板
  - `SKILL.md` —— 文档已同步

---

## 七、增量修复：骨密度检测别名（2026-04-20）

### 问题

Mac 上第三轮 `run_verify.command` 输出：

- `test/1/report.md`：Excel `骨密度` ↔ OCR `骨密度` → 11 条 `exact` 匹配（OK）；另有 2 个方案里 OCR 识别到 `骨密度` 但 Excel 该方案未列 → 合理「多余」
- `test/2/report.md`：OCR `骨密度检测` vs Excel 方案-女已婚未列任何骨密度 → 合理「多余」

### 根因分析

- 源代码**无**任何针对 `骨密度/骨密度检测` 的 alias / rename / composite 规则
- 潜在盲区：若某方案 Excel=`骨密度`（3 字）/ OCR=`骨密度检测`（5 字）同时出现：
  - L1 `exact/alias` 不命中
  - L2 `fuzzywuzzy.ratio` ≈ 75 < 85 阈值，不命中
  - L3 LLM 可以兜住，但仅在 Gemini/Claude 在线时生效
  - L3 关闭时会产生「缺失 + 多余」的假报

### 修复

在 `config/default_rules.json.aliases` 增加：

```json
["骨密度检测", "骨密度"]
```

版本号：`1.0.6 → 1.0.7`，`last_updated = 2026-04-20`

### 沙盒回归（三场景全通过）

| 场景 | Excel | OCR | 期望 | 实际 |
|---|---|---|---|---|
| S1 | `['骨密度','血压']` | `['骨密度检测','血压']` | 两条均匹配（alias + exact） | ✅ 一条 `alias`、一条 `exact` |
| S2 | `['骨密度']` | `['骨密度']` | `exact`（回归） | ✅ `exact` |
| S3 | `['血压']` | `['骨密度检测']` | 缺失+多余（不被误吞） | ✅ 1 缺失 + 1 多余 |

### 修改范围

- `skills/medical-exam-checker/config/default_rules.json` —— 版本号、时间戳、aliases 追加一条
- `skills/medical-exam-checker/SKILL.md` —— 规则配置示例补充 `骨密度检测`；新增「添加别名的判断标准」小节
- `VERIFY_REPORT.md` —— 新增本节

### 副作用分析

- 仅影响 L1 别名归一，对其他体检项无影响
- `build_alias_map` 用 BFS 合并等价类，`骨密度` 作为 `preferred` 被选为 canonical（规则：优先 `preferred` 集合 + 字符最短）
- 零新增运行时开销，零新增网络调用

### 何时应追加新别名

参考 `SKILL.md > 规则配置示例 > 添加别名的判断标准`。触发条件：**字长差 ≥ 3 字 + 业务 100% 等价 + 想零 LLM 成本解决**。
