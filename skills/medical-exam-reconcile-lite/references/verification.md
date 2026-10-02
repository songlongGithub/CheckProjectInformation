# 可复现验证

## 1. 本包自身回归（零第三方依赖）

在 skill 目录运行：

```bash
python3 -S -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py
```

使用 `-S` 禁止加载 site-packages，可直接验证运行时无外部依赖。单测均为合成数据，不携带客户图/Excel/逐字转录。

覆盖精确/传递别名/重复项目消费/缺失多余/模糊待复核/组合不完整/标题同分与性别冲突/转录不确定/单图和全批失败/空输入/严格规则校验/合并标题真实列坐标/无缓存公式/输出保护/异常ZIP/XML及UTF16 DTD拒绝/CLI退出码。

## 2. 复用原项目测试与真实Excel

检出原仓库快照，保持源码和 expected 不变：

```bash
git clone https://github.com/songlongGithub/CheckProjectInformation.git upstream
git -C upstream checkout 1392fcc2cf9451467b40f0be4e840a274967a481
python3 -m venv .reference-venv
.reference-venv/bin/python -m pip install pandas==2.2.3 openpyxl==3.1.5 fuzzywuzzy==0.18.0 python-Levenshtein==0.23.0 requests==2.34.2 pytest==9.1.1
.reference-venv/bin/python -m pytest -p no:cacheprovider upstream/test_ocr_parsing.py upstream/test_smart_matching.py -v
.reference-venv/bin/python tests/verify_project.py --project upstream --output project-regression.json
```

这些依赖仅为运行原项目作参考，不是本Skill运行依赖。上游其余test_update类会联系更新服务，不能与核心离线测试混为一谈；这里不执行。

`verify_project.py` 会：
- 将原 `test_ocr_parsing.py` 的11个原测试函数/29条断言原样运行在本Skill接口上，只有返回形状适配，不改输入或expected
- 对4份原始Excel核对完整方案与项目顺序；原Skill有首行列宽探测缺陷，因此同时记录未改基线，并单独在测试中仅修正该probe、再与Skill逐项对照
- 对所有68个方案运行项目列表差分；仅把fuzzy状态按明确政策从“匹配”映射为“需复核”，匹配对象、类型与其余字段不变
- 用94个实际项目名称两两对比2种相似度算法，共17672项，确保stdlib实现与带Levenshtein的原scorer一致
- 子进程用 `python -S` 运行本Skill CLI解析真实Excel
- 禁止测试进程的网络连接；只写脱敏计数、输入/输出摘要SHA，不输出客户清单

`test_smart_matching.py` 的4个函数只打印演示，没有断言。因此“15 passed”不能表述为15个准确性测试；严谨写法为“11项断言测试通过，另4项演示执行成功”。

## 3. 全量原图主路径

先在用户授权的本地环境，逐图独立视觉提取为 contract.md 的 JSON；转录者不读Excel预期项，不根据核对差异改字。必须实际看像素，正确区分选中方案与界面其他列表行，标注截断/模糊处。

转录文件以原图stem命名放在一个私有目录，再运行：

```bash
.reference-venv/bin/python tests/verify_project.py --project upstream --vision-dir /私有转录目录 --output vision-regression.json
```

脚本要求26张图各有输入，经实际CLI核对后，每图均有状态、方案数、分项计数和来源SHA。退出1可能是正确发现差异/待复核，不等于失败；反之退出0也不是图片人工准确率结论。该次宿主视觉转录是独立提取输入，不是双人独立裁决的金标准。

可选 `--local-ocr-dir` 仅复现本次Tesseract兼容路径（目录中需 private-manifest.json）；它依赖另行本地OCR运行，不属于Skill运行依赖。现有百度布局提取不保证与其他OCR引擎兼容。本次本地OCR主文件成功26份但兼容核对无法定位，必须如实报告，不拿“进程成功”当业务通过。

## 隐私与结果解释

原图、Excel、OCR全文、视觉转录、完整客户核对报告、凭据都不打入交付包。交付只含源码、合成测试、复现方法及计数报告；需要复现原始数据时从用户已授权原仓库获取。测试不是临床验证，不证明图片识别零遗漏，也不证明机构规则适用于所有人。
