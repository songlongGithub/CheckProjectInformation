---
name: medical-exam-checker
description: 体检方案智能核对——用 Excel 体检方案对比图片（体检订单截图）OCR 识别的结果。触发条件：用户上传体检方案 Excel (xlsx) 和体检订单图片 (jpg/jpeg/png)，请求"核对"、"比对"、"找出差异"、"确认项目"。支持一张图片含多个方案的场景，逐方案输出匹配/缺失/多余项。三层匹配：规则（alias+精确）→ fuzzy（85 阈值）→ LLM 语义（默认 Gemini，可切 Claude，可关闭）；composites 处理"父项覆盖子项"业务包含关系（如"妇科检查"覆盖"白带常规"）。不适用于：非体检场景的 Excel 对比、PDF 输入、手写体识别、无百度 OCR 凭据的纯离线识别。
metadata:
  short-description: 体检方案 Excel × 体检订单图片 OCR 自动核对，三层匹配 + composites 父子项展开，输出 JSON / Markdown / 聊天文本。
  why: 体检机构订单截图与客户方案表常对不齐（漏项/多项/术语不同），人工核对慢且易漏；尤其同一项目在 OCR 侧可能聚合（"肝功全套"）也可能展开为多个子项（"肝功两项 + 蛋白四项 + 胆红素三项 + GGT..."），纯字符匹配无能为力。
  what: 解析 Excel 方案分类 + 百度 OCR 识图抽项 + 三层匹配（规则/模糊/LLM）+ 父子复合项双向展开 + 输出 4 种格式报告（完整 JSON / 完整 Markdown / 精简差异 Markdown / 聊天 bot 紧凑文本）。
  how: Python + pandas/openpyxl 解析 Excel（状态机按男/女未婚/女已婚分类）；百度 OCR accurate_basic 识字；fuzzywuzzy 模糊匹配（阈值 85）；Gemini 2.0 Flash / Claude Haiku 语义兜底（可关）；composites 规则双向处理"父项-子项"业务包含关系。
  results: 逐方案输出匹配 / 缺失 / 多余，完美匹配免复核，部分匹配只列差异行；match_type 字段可追溯（exact / alias / fuzzy / composite / llm）。
  version: 1.0.9
  updated: '2026-04-22'
  jtbd-1: 体检机构把订单截图发给我后，我要核对是否和已签的 Excel 方案一致，希望自动出差异报告，我只看需要人工判断的条目。
  jtbd-2: 聊天机器人收到体检订单图片，要立即输出"完美 / 需复核 / 未匹配方案"三类摘要，紧凑且无 markdown 表格（IM 渲染兼容）。
  audit:
    kind: module
    author: songlongGithub
    category: Document Processing
    permissions:
      file-read: true       # Excel / 图片 / credentials.json / default_rules.json
      file-write: true      # 报告（--output / --markdown / --markdown-diff / --chat-output）+ 缓存（--ocr-cache-dir / --llm-cache-dir）
      network: true         # 百度 OCR API（必需）+ Gemini / Claude API（可关）
      shell: false
    network-endpoints:
      - aip.baidubce.com                    # 百度 OCR accurate_basic
      - generativelanguage.googleapis.com   # Gemini（可选，--no-llm 可关）
      - api.anthropic.com                   # Claude（可选，--llm-provider claude）
    data-boundaries:
      - 仅读取本地 Excel/图片/凭据；除 OCR/LLM 调用外无任何对外传输
      - 所有写入限定在用户显式指定路径（--output / --markdown / --ocr-cache-dir 等）
      - 不修改系统文件、不执行 shell 命令、不持久化任何全局状态
---

# Medical Exam Checker Skill

## 用途

把 Excel 里定义的体检方案与体检订单图片中的项目进行自动化核对，输出每张图片对应的差异报告。

核心场景：客户拿到 Excel 方案表，又从体检机构收到订单截图，需要核对"订单里有没有漏项 / 多项"。

## 什么时候触发这个 skill

- 用户同时提供了 **体检方案 Excel** 和一张或多张 **体检订单图片**
- 用户要求："核对体检项目 / 比对 Excel 和图片 / 找出差异项 / 看看有哪些漏检多检"
- 一张图片可能包含 2~N 个方案（例如男员工方案 + 女员工方案），skill 会逐方案输出
- 用户只给 Excel 想先看分类：走 `--excel-only` 分支

## 不适用

- 非体检业务的 Excel/图片对比
- PDF/手写体/非百度 OCR 的图片源
- 没有百度 OCR 凭据且没有 OCR 缓存的纯离线场景（需要至少一次联网拿缓存）

## 快速上手

### 前置条件

1. Python 3.9+（`pandas / openpyxl / requests / fuzzywuzzy`，首次运行时 skill 会**自动建 venv 并装依赖**，无需手动 `pip install`）
2. 百度 OCR 凭据（优先级：CLI 参数 > `OCR_API_KEY/OCR_SECRET_KEY` 环境变量 > `config/credentials.json`）

### 依赖自动安装

`scripts/check.py` 和 `scripts/ocr_image.py` 入口含 bootstrap：

- 首次运行 → 在 skill 目录下创建 `.venv`、`pip install -r requirements.txt`、再 `os.execv` 自己进入 venv
- 后续运行 → 检测到 venv 已就绪（sentinel `.venv/.bootstrap-done`），直接 re-exec，毫秒级开销
- 不污染系统 Python；`npx skills update` 后若 venv 被清，下次自愈

首次运行会打印到 stderr：

```
[bootstrap] Setting up skill venv at .../.venv (one-time, 1-2 min) ...
[bootstrap] Venv ready; re-executing under .../.venv/bin/python
```

### 三条核心命令

**A. 只解析 Excel，快速预览方案分类（离线，无需凭据）**

```bash
python scripts/check.py \
  --excel path/to/方案.xlsx \
  --excel-only \
  --output schemes.json
```

输出 `schemes.json`：每个 `(sheet, category)` 组合的项目列表。

**B. 对单张图片跑 OCR 与抽方案（只出 OCR 结果，不做对比）**

```bash
python scripts/ocr_image.py \
  --image path/to/order.jpg \
  --output ocr.json
```

输出 `ocr.json`：每张图一条 `{file, status, ocr_schemes:[{title, items}], raw_words}`。

**C. 端到端核对：Excel + 一批图片 → 完整报告（默认 Gemini）**

```bash
# 默认走 Gemini LLM 兜底；凭据探测 GEMINI_API_KEY / GOOGLE_API_KEY / credentials.json
python scripts/check.py \
  --excel path/to/方案.xlsx \
  --images path/to/*.jpg \
  --output report.json \
  --markdown report.md
```

**输出格式（四种可同时开启）**

| flag | 适用场景 | 体积 |
|---|---|---|
| `--output <json>` | 程序消费、审计留痕、完整契约 | 大 |
| `--markdown <md>` | 人工全量核对、逐行可追溯 | 大 |
| `--markdown-diff <md>` | 核对人员复核、只看差异 | 小 |
| `--chat-output <txt>` | 聊天 bot / IM 机器人转发通知 | 极小 |

一次跑完可同时产出多种：

```bash
python scripts/check.py \
  --excel 方案.xlsx \
  --images photos/*.jpg \
  --output report.json \
  --markdown report.md \
  --markdown-diff report_diff.md \
  --chat-output report_chat.txt
```

**LLM 开关：**

```bash
# 关闭 LLM 层（纯规则+fuzzy）
python scripts/check.py ... --no-llm

# 切到 Claude
python scripts/check.py ... --llm-provider claude --llm-model claude-haiku-4-5

# 显式传 Gemini Key
python scripts/check.py ... --gemini-key $YOUR_KEY

# LLM 响应缓存（复跑零成本）
python scripts/check.py ... --llm-cache-dir .llm_cache/
```

**节省 OCR 配额（--ocr-cache-dir）**：第一次跑会写缓存，后续重跑（调规则、调阈值）直接读缓存不走网络：

```bash
python scripts/check.py \
  --excel 方案.xlsx \
  --images test/1/*.jpeg \
  --ocr-cache-dir test/1/.ocr_cache/ \
  --output test/1/report.json \
  --markdown test/1/report.md
```

## 输出契约（核对报告 JSON）

```json
{
  "generated_at": "2026-04-20T14:30:00",
  "excel": {
    "file": "方案.xlsx",
    "sheets_in_order": ["方案一", "方案二"],
    "schemes": [
      {"sheet": "方案一", "category": "男", "items": ["身高体重", "血压", ...]},
      {"sheet": "方案一", "category": "女已婚", "items": [...]}
    ]
  },
  "images": [
    {
      "file": "order_001.jpg",
      "path": "test/1/order_001.jpg",
      "status": "ok | ocr_failed | no_scheme_detected",
      "error": null,
      "ocr_schemes": [
        {
          "index": 1,
          "ocr_title": "方案一(男)",
          "matched_excel_scheme": "方案一 - 男",
          "confidence": 97,
          "verdict": "perfect | partial | no_match",
          "stats": {
            "matched": 30, "missing": 2, "extra": 1,
            "total_excel": 32, "total_ocr": 31
          },
          "comparison": [
            {"excel": "身高体重", "ocr": "身高体重", "status": "匹配", "match_type": "exact"},
            {"excel": "C14呼气试验", "ocr": "碳十四呼吸检测", "status": "匹配", "match_type": "alias"},
            {"excel": "血糖", "ocr": "【缺失】", "status": "缺失", "match_type": null},
            {"excel": "【多余】", "ocr": "骨密度", "status": "多余", "match_type": null}
          ]
        }
      ]
    }
  ],
  "summary": {
    "total_images": 5,
    "images_ok": 4,
    "images_ocr_failed": 1,
    "images_no_scheme": 0,
    "perfect_matches": 3,
    "partial_matches": 2,
    "no_match_schemes": 0
  }
}
```

**关键字段**

- `images` 数组：每张图都有一条，**一定不缺**
- `images[].ocr_schemes` 数组：按 OCR 在图中的出现顺序，`index` 从 1 起；一图多方案时依次排列
- `verdict`：`perfect`（零差异）/ `partial`（有缺失或多余）/ `no_match`（方案名没匹配上 Excel）
- `match_type`：
  - `exact` 原名字符相同
  - `alias` 走别名映射匹配
  - `fuzzy` fuzzywuzzy 模糊匹配（≥85）
  - `llm` LLM 语义匹配（默认 Gemini）；附 `reason` 字段含 confidence 与理由
  - `composite` 父项覆盖子项（业务包含关系）；`ocr` 列显示 `∈<父项>`
- `summary`：图片级 + 方案级双维度聚合，方便大模型快速回答"整体情况如何"

## 一图多方案呈现示例（Markdown）

```markdown
### 图片 1: `order_001.jpg` [OK]

识别出 2 个方案：**方案一(男)** → 方案一 - 男; **方案一(女已婚)** → 方案一 - 女已婚

#### ① 方案一(男) ↔ 方案一 - 男 (置信度 97)

- 结果: ✅ 完美匹配
- 统计: 匹配 30 / 缺失 0 / 多余 0

| Excel 项 | OCR 项 | 状态 |
|---|---|---|
| 身高体重 | 身高体重 | ✅ 匹配 |
| ... | ... | ... |

#### ② 方案一(女已婚) ↔ 方案一 - 女已婚 (置信度 95)

- 结果: ⚠️ 部分匹配
- 统计: 匹配 28 / 缺失 2 / 多余 1
```

## 核心规则摘要（便于大模型理解阈值与取舍）

1. **Excel 解析**：读取 A/B/C/E/F 共 5 列；A 列出现"项目或组合"作为数据起点；遇"健康管理"停止。
2. **状态机**：按行文本切换 NORMAL / MALE / FEMALE_UNMARRIED / FEMALE_MARRIED / FEMALE_MARRIED_H / FEMALE_GENERIC；"标准早餐"作为任一区块结束符。
3. **项目名选取**：套餐关键字（全套/套餐/肝功十三项等）→ 整组取主项目名并去重；否则 B 列优先，其次 A 列。
4. **性别归属三级优先**：E/F 列 `√` → 当前区块 → NORMAL 默认男女通用。
5. **组合模型**：通用桶 + 专属桶组合；仅当专属桶非空才生成对应方案类别。FEMALE_GENERIC 区块默认全进已婚；剔除婚育关键字命中项后再进未婚；乳腺/盆腔彩超豁免。
6. **重命名 vs 别名 vs composites**（三种规则各司其职）：
   - 重命名（`renames`）：在 **解析 Excel 阶段** 改写/拆分真·同义表达（如"一般检查"→"身高体重,血压,放射项目不出胶片,超声项目不出片"）
   - 别名（`aliases`）：在 **对比阶段** 归一等价类（canonical 选最短+字典序最小）
   - Composites（`composites`）：在 **对比阶段 L4** 展开主-子包含关系。父项匹配成功 → 子项自动标 `match_type=composite`，OCR 列显示 `∈<父项>`。典型场景：OCR 订单只列"妇科检查"，而 Excel 里"妇科检查"业务覆盖"白带常规"——composites 声明这关系后，白带常规不再被误报缺失
7. **方案名匹配**（阈值 **95**）：去噪声括号 → 组件化拆分 → 性别/婚姻标签筛候选 → token_sort_ratio
8. **逐项对比三层匹配**：
   - **L1** alias 归一 + 字符精确（match_type=exact/alias）
   - **L2** Fuzzy（`fuzz.ratio ≥ 85`，match_type=fuzzy）
   - **L3** LLM 语义（可选；默认 Gemini；supports 一对多；confidence ≥ 0.7 采纳；match_type=llm；附 reason）
   - **L4** composites 展开（父项已命中 → 子项追加，match_type=composite）
   - **L5** 剩余 → 缺失/多余
9. **LLM 降级策略**：LLM 层任何异常（超时、JSON 解析失败、凭据缺失）自动降级到仅规则+fuzzy，不阻塞主流程。

## 凭据来源优先级

### 百度 OCR

| 优先级 | 来源 | 说明 |
|---|---|---|
| 1 | `--api-key/--secret-key` | CLI 参数，显式最高 |
| 2 | `OCR_API_KEY/OCR_SECRET_KEY` | 环境变量 |
| 3 | `--credentials <path>` | JSON 文件，默认读 `config/credentials.json` |

### LLM（Gemini 默认 / Claude 可切）

| 优先级 | 来源（Gemini） | 来源（Claude） |
|---|---|---|
| 1 | `--gemini-key` | `--claude-key` |
| 2 | `GEMINI_API_KEY` > `GOOGLE_API_KEY` | `ANTHROPIC_API_KEY` > `CLAUDE_API_KEY` |
| 3 | `credentials.json.gemini.api_key` | `credentials.json.claude.api_key` |

凭据找不到时，LLM 层自动关闭，核对降级到规则+fuzzy。

`credentials.json` 完整格式：

```json
{
  "baidu_ocr": {
    "api_key": "...",
    "secret_key": "..."
  },
  "gemini": {
    "api_key": "..."
  },
  "claude": {
    "api_key": "..."
  }
}
```

## 常见问题排查

- **"Failed to obtain Baidu OCR access token"**：凭据错了或网络不可达。先 `curl https://aip.baidubce.com` 确认联通性。
- **`no_match_schemes` 偏高**：OCR 标题里含"（紫单不可替）"等噪声被正确剔除，但若仍无匹配，检查 Excel 的 sheet 命名是否含"方案"字样，阈值 95 可能过严——临时把 `matcher.py` 的 `SCHEME_MATCH_THRESHOLD` 调到 90 再跑。
- **某项应当被视为同义词，但显示"缺失+多余"**：在 `config/default_rules.json` 的 `aliases` 追加 `["OCR 识别名", "Excel 标准名"]`。
- **OCR 识别到杂项**（"单见名单不可替检）"）：这类会被 `_parse_multi_scheme` 的杂项清单跳过；若仍出现，编辑 `ocr_extractor.py` 的 `{"检)", "检）", "分组名称：", ...}` 列表。
- **图片分辨率太低**：百度 accurate_basic 要求图片宽高不小于 15px 且不大于 4096px；过小建议上采样。

## 目录结构

```
skills/medical-exam-checker/
├── SKILL.md                  # 本文件
├── requirements.txt          # 核心依赖（无 PyQt6）
├── config/
│   ├── default_rules.json    # 别名/重命名/性别重命名/composites
│   ├── credentials.json      # （gitignored）OCR + LLM 凭据
│   └── credentials.example.json
└── scripts/
    ├── ocr_image.py          # CLI 1：单图 OCR + 抽方案
    ├── check.py              # CLI 2：端到端核对（含 --no-llm / --llm-provider 开关）
    └── core/
        ├── excel_parser.py   # Excel 解析 + 状态机 + 组合模型
        ├── ocr_client.py     # 百度 OCR 客户端 + 磁盘缓存
        ├── ocr_extractor.py  # OCR JSON → [(title, items), ...]
        ├── matcher.py        # 三层匹配：规则 → fuzzy → LLM + composites 展开
        ├── llm_client.py     # LLM 抽象（GeminiClient / ClaudeClient）+ 响应缓存
        ├── rules.py          # 规则与 OCR/LLM 凭据加载
        ├── reporter.py       # JSON 契约 + Markdown 渲染（含 reason 列）
        └── logger.py         # 统一日志格式
```

## 阈值与进阶调参

- `matcher.SCHEME_MATCH_THRESHOLD`：默认 95，控制方案名匹配严格度
- `matcher.ITEM_MATCH_THRESHOLD`：默认 85，控制逐项对比（L2）严格度
- `matcher.LLM_CONFIDENCE_THRESHOLD`：默认 0.7，控制 LLM 匹配采纳阈值
- `excel_parser._MARITAL_STATUS_KEYWORDS`：女性必归已婚的关键词
- `excel_parser._PACKAGE_KEYWORDS`：套餐整合关键词

任意阈值调整后，建议用 `--ocr-cache-dir` + `--llm-cache-dir` 做离线回归，避免重复消耗 API。

## 规则配置示例（composites）

```jsonc
{
  "aliases": [
    ["碳十四呼吸检测", "C14呼气试验"],
    ["骨密度检测", "骨密度"]   // OCR 扫成 5 字长名，Excel 标准名只 3 字
  ],
  "renames": [["一般检查", "身高体重,血压,放射项目不出胶片,超声项目不出片"]],
  "gender_renames": [["外科检查", "外科检查(男)", "外科检查(女)"]],
  "composites": [
    {
      "parent": "妇科检查",
      "children": ["白带常规"],
      "note": "妇科检查业务上覆盖白带常规交费项，OCR 订单通常只列父项"
    }
  ]
}
```

### 添加别名的判断标准

当对比报告里某项同时出现「缺失 + 多余」且两者表达同一体检项时，优先通过 `aliases` 解决：

1. 字符长度差 ≥ 3 字 → fuzzywuzzy ratio 会跌破 85 阈值（如 `骨密度` vs `骨密度检测`：3 字 vs 5 字）
2. 业务上 100% 等价（不存在"哪种叫法更精确"的语义歧义）
3. 无需 LLM 语义层兜底（零运行时成本）

加到 `config/default_rules.json.aliases` 末尾，**无需改代码**。格式：`["OCR 识别名", "Excel 标准名"]`。

**composites vs renames 的取舍**：若 OCR 侧只会出现父项、Excel 侧需要独立记录子项以便对账——用 `composites`；若两侧都会出现拆分后的多个独立项名——用 `renames`。不要再用 `["X","SELF,Y"]` 这种老写法（单侧膨胀会造成 Y 误报缺失）。
