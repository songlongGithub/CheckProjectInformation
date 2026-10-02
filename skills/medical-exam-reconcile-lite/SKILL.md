---
name: medical-exam-reconcile-lite
description: 轻量离线核对体检套餐 Excel 与订单截图中已提取的项目清单，定位缺项、多项和待复核关系。适用于体检方案核对、套餐与订单比对、原项目回归；不作疾病诊断或医疗建议。
---

# 体检套餐轻量核对

把客户方案与机构订单当作两份业务清单核对。项目的性别/婚姻分类、别名和包含关系属于机构业务配置，不能当成普适医学事实。

## 输入与边界

- Python 3.10+，运行只用标准库，无 pip、GUI、服务或 API Key
- 必需：`.xlsx` 方案；完整核对还需订单图片或已提取的本地 JSON
- 用户只要查看方案时用 `--excel-only`
- 图片由当前宿主的视觉能力读取，或使用用户已提供/授权的 OCR 文本。脚本不直接识图、不联网，也不会搜寻或读取凭据
- 不支持 `.xls`、PDF、扫描 Excel、手写或未经换算的不同表格模板；遇不支持输入说明具体缺项

## 工作方法

1. 用 `scripts/check.py --excel 文件.xlsx --excel-only` 检查方案、类别和项目数。解析按 A/B/C/E/F 实际坐标，非首行列宽；源格式和规则见 [references/contract.md](references/contract.md)
2. 对每张图片独立提取标题、逐项名称和不确定处，保存为契约 JSON。一图多方案逐个保留。先看图再核对，不以 Excel 的预期项目补字、不擅改看不清的内容；数字、数量、部位和 H/CT 等限定必须保留。无法辨认时列 uncertainties，请求清晰图片
3. 运行离线核对。标准化/重命名仅来自明确规则；输出需同时保留来源和 `match_type`
4. 汇报缺失、多余、未确定方案、输入失败以及所有 fuzzy/composite 候选。标题相似分不是识别置信概率。同分方案不能替用户选一个
5. `no_difference_in_supplied_text` 只表示提供的文本无差异，不证明截图已完整识别。只要任一输入失败、不确定、模糊或组合候选未确认，就不能写“全部一致/无需复核”

完整命令（路径相对 skill 目录）：

```bash
python3 scripts/check.py --excel 方案.xlsx --ocr-json 订单1.json 订单2.json --output 核对.json --text-output 差异.txt
```

只解析：

```bash
python3 scripts/check.py --excel 方案.xlsx --excel-only --output 方案.json
```

退出码：0=所提供文本一致或Excel解析完成；1=存在差异/待复核/未确定方案；2=输入或解析错误。1不代表脚本崩溃；读取已生成报告继续复核。输出路径须显式指定，省略则 JSON 写 stdout。

## 规则与复核

- 内置 `config/default_rules.json` 保留原项目 v1.1.0 的 43 个别名对、3 个重命名、1 个性别重命名、3 个组合定义
- 精确/别名是一对一；fuzzy 阈值85仅给候选；composites 保存原关系但一律待复核，不能用“任一子项”证明整个套餐覆盖
- 用户确认某业务等价后，可在其指定的规则副本增加 aliases，并用 `--rules 副本.json` 重跑；不要从一次相似名称推导永久业务规则
- 核对期间不上传健康数据、不发第三方消息、不修改源 Excel 或图片

开发/验证本 skill 时读 [references/verification.md](references/verification.md)。来源与已知限制见 [references/provenance.md](references/provenance.md)。
