# 来源与范围

基于用户仓库 https://github.com/songlongGithub/CheckProjectInformation ，main 快照 `1392fcc2cf9451467b40f0be4e840a274967a481`（2026-05-07）中 `skills/medical-exam-checker` v1.1.0。

- OCR提取和规则/方案匹配核心从现有实现精简；保留默认规则内容
- Excel读取改为标准库ZIP/XML，移除pandas/openpyxl；采用实际A/B/C/E/F单元格坐标，修复首两行合并标题导致旧实现只读1/3列的问题
- fuzzy只保留用到的Levenshtein归一化indel/LCS分数和token-sort流程，移除fuzzywuzzy/Levenshtein依赖
- 移除百度/LLM客户端、凭据探测、网络缓存、自动venv/pip和GUI/Web层
- 同分方案停止自动选择；fuzzy/composite都要求复核；空输入/失败不能“完美”

本包是用户要求的独立本地交付，未改原仓库、未push/PR/部署、未全局安装。原README声明MIT，但快照未包含独立LICENSE文件；这里保留来源说明，不替源作者另授许可证。

## 尚有边界

保留原版区块分类、套餐去重、重命名与OCR布局假设；并非所有Excel模板都支持。尤其跨区块同名套餐、纯通用项目、异常勾选与区块冲突需人工检查。非标准模板不要降低匹配阈值强行适配。

内置composites含多种OCR写法，不是“必选子项全集”。因此不能把所有children必须出现当作新的医学业务标准，也不能任取一项判整个父套餐完整；本版将关系候选交人工复核。

本包测试仅证明指定软件行为、已知语料兼容和错误可见性。没有医学诊断正确性保证，也没有完整的人标图片准确率验证。
