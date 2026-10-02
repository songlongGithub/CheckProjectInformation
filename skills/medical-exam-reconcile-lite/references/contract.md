# 输入输出契约

## Excel

A=项目或组合，B=子项目，C=明细，E=男，F=女。A列去空格后为“项目或组合”起读，A含“健康管理”停止；支持正常 xlsx sharedStrings/inlineStr、合并标题（按真实坐标读取，不向下填充合并单元格）。不计算公式；必要列有无缓存公式或 Excel 错误值则拒绝，先在 Excel 重算保存。

按 A+B 切换男性、女未婚、女已婚、女已婚H、女性通用和标准早餐重置区块。勾选仅识别 `√`；缺勾选时沿用区块；普通区块默认男女通用。套餐父项优先，否则B优先A次之；重命名后分类，再做性别重命名，最终按原行序去重。

类别仅在有对应专属项目时生成。通用女区块的婚育关键词及乳腺/盆腔豁免沿用上游业务配置；不擅自扩展到其他格式。纯通用清单无法生成方案会显式报错。

## 图片提取 JSON（推荐）

```json
{
  "source": "订单.png",
  "extraction_method": "host_vision",
  "schemes": [
    {"title": "方案一男", "items": ["项目甲", "项目乙"], "uncertainties": []}
  ]
}
```

每个输入 JSON 对应一张图，一图多方案扩展 schemes。items 不得参考 Excel 补齐；截断/模糊/缺页都写 uncertainties。不能看图则请用户给已有文本，不宣称已经完成OCR。

也接受原项目百度格式 `{"words_result":[{"words":"一行文本"},...]}`。这条兼容路径保留原版 marker/layout 假设：单方案用“自定义选项→分组信息”，多方案用“分组价格→分组交费”拼行并按顿号分项目。其他 OCR 引擎的分行/空格不能保证兼容，可从原图按推荐结构重提取。原文提取失败不等于“没有差异”。

## 报告

- documents 每个输入一条，status=`ok|invalid_input|no_scheme_detected`
- schemes 中 `matched_scheme` 和 `score` 代表唯一候选与标题相似分（>=95），无匹配或同分时为空
- verdict=`no_difference_in_supplied_text|differences|needs_review|no_match`
- comparison 每行含 excel_item、ocr_item、status、match_type、reason
- status=`匹配|缺失|多余|需复核`；match_type=`exact|alias|fuzzy|composite|null`
- fuzzy/composite 行沿用原关系候选，一律标需复核，不计入确认匹配；方案级 review_reasons 必须展示
- summary.status=`text_consistent|review_required|input_error`；图片失败优先，不允许被其他一致方案掩盖

规则可用 `--rules` 指定 JSON；不支持脚本表达式，不自动改规则。每次只读取显式指定输入与内置规则。ZIP大小、XML实体、输出覆盖输入均有防护。对不支持格式的拒绝是有意行为。
