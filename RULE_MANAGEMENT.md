# 规则管理系统使用说明

## 概述

本系统提供了灵活的规则管理方案，解决了原有硬编码规则的问题，支持：

- ✅ 外部配置文件存储规则
- ✅ CSV 格式导入导出（可用 Excel 编辑）
- ✅ 在线规则库更新
- ✅ 用户自定义规则
- ✅ 版本管理和兼容性

## 架构设计

### 1. 规则文件结构

规则存储在 `default_rules.json` 文件中，格式如下：

```json
{
  "version": "1.0.0",
  "last_updated": "2025-10-17",
  "aliases": [
    ["OCR识别名", "Excel标准名"],
    ["静脉采血", "采血"]
  ],
  "renames": [
    ["原项目名", "新项目名1,新项目名2"]
  ],
  "gender_renames": [
    ["原项目名", "男性新名", "女性新名"]
  ]
}
```

### 2. 三种规则类型

#### 别名规则 (aliases)
用于对比阶段，将 OCR 识别的不规范名称映射到 Excel 标准名称。

**示例：**
- `["静脉采血", "采血"]` - OCR 识别为"静脉采血"时，映射为"采血"
- `["碳十三呼气检查", "C13"]` - 将长名称映射为简称

#### 重命名规则 (renames)
用于解析 Excel 阶段，改写或拆分项目名称。支持 `SELF` 关键字保留原名。

**示例：**
- `["一般检查", "身高体重,血压,放射项目不出胶片,超声项目不出片"]` - 拆分为多个子项
- `["妇科检查", "SELF,白带常规"]` - 保留原名并添加子项

#### 性别规则 (gender_renames)
根据性别分类使用不同名称。

**示例：**
- `["外科检查", "外科检查（男）", "外科检查（女）"]`

## 使用方法

### 方法一：通过 GUI 管理规则

1. **打开设置对话框**
   - 启动应用后，点击"设置"按钮
   - 切换到相应的规则标签页

2. **直接编辑规则**
   - 在表格中直接修改现有规则
   - 使用 ➕ 按钮添加新规则
   - 使用 ➖ 按钮删除选中规则
   - 点击"保存"按钮应用更改

3. **导出为 CSV**
   - 点击 📤 "导出为CSV" 按钮
   - 选择导出目录
   - 系统会生成三个 CSV 文件：
     - `aliases.csv` - 别名规则
     - `renames.csv` - 重命名规则
     - `gender_renames.csv` - 性别规则

4. **从 CSV 导入**
   - 使用 Excel 编辑导出的 CSV 文件
   - 点击 📥 "从CSV导入" 按钮
   - 选择包含 CSV 文件的目录
   - 系统会自动加载并更新规则

5. **在线更新**
   - 点击 🔄 "在线更新规则" 按钮
   - 系统会从云端获取最新规则库
   - 仅更新默认规则，用户自定义规则不受影响

### 方法二：直接编辑 JSON 文件

1. 打开项目目录下的 `default_rules.json` 文件
2. 按照 JSON 格式编辑规则
3. 保存文件后重启应用即可生效

**优点：** 批量编辑更方便，支持版本控制

### 方法三：使用 CSV 文件（推荐非技术人员）

1. 导出当前规则为 CSV 文件
2. 使用 Excel 打开并编辑
   - 注意保存为 UTF-8 编码
   - 不要删除表头行
3. 将编辑好的 CSV 文件放在同一目录
4. 通过 GUI 导入即可

## 高级功能

### 1. 规则版本管理

系统会自动跟踪规则版本：
- `version` 字段记录当前版本号
- `last_updated` 字段记录最后更新时间
- 在线更新时会比较版本号，只有更新的版本才会覆盖

### 2. 规则合并策略

当用户自定义规则与默认规则冲突时：
- 用户规则优先级更高
- 新的默认规则会自动合并到用户规则中
- 不会覆盖用户已修改的规则

### 3. 规则库在线更新

#### 搭建规则服务器

可以搭建一个简单的规则服务器来提供在线更新：

```python
# 示例：使用 Flask 提供规则服务
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/medical_rules.json')
def get_rules():
    with open('default_rules.json', 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    app.run(port=8080)
```

然后在 `settings_dialog.py` 中配置服务器 URL：
```python
online_url = "http://your-server.com:8080/medical_rules.json"
```

### 4. 团队协作

**场景：** 多个用户共享规则库

1. 将 `default_rules.json` 放在共享网络位置
2. 每个用户定期执行"在线更新"
3. 或者使用版本控制系统（如 Git）同步规则文件

## 智能匹配方案（方案二）

除了规则管理，系统还可以使用智能模糊匹配来减少规则数量：

### 实现原理

```python
from fuzzywuzzy import fuzz, process

def smart_match(ocr_text, excel_items, threshold=85):
    """使用模糊匹配自动查找最佳匹配项"""
    best_match, score = process.extractOne(
        ocr_text, 
        excel_items, 
        scorer=fuzz.token_sort_ratio
    )
    
    if score >= threshold:
        return best_match
    return None
```

### 优势

- **自动适应新项目**：不需要为每个新项目添加规则
- **容错性强**：可以处理 OCR 识别错误
- **减少维护成本**：规则库更小，更易维护

### 组合使用建议

1. **优先使用规则匹配**：对于常见的、固定的别名
2. **智能模糊匹配作为补充**：处理规则库中没有的项目
3. **用户反馈学习**：将匹配结果添加到规则库中

## 最佳实践

### 1. 规则命名规范

- **别名规则**：左侧填写 OCR 可能识别的名称，右侧填写标准名称
- **重命名规则**：使用英文逗号分隔多个子项
- **性别规则**：确保男女两列都有内容，不要留空

### 2. 定期维护

建议每月检查一次规则库：
1. 导出为 CSV 格式
2. 检查是否有重复规则
3. 删除过时或无效的规则
4. 添加新发现的别名

### 3. 备份规则

在大量修改规则前：
1. 导出当前规则为 CSV（作为备份）
2. 或复制 `default_rules.json` 文件
3. 修改完成后测试验证

### 4. 团队分工

- **医疗专家**：负责维护医学术语的标准名称
- **技术人员**：负责维护 OCR 识别别名和系统配置
- **最终用户**：反馈匹配问题和改进建议

## 故障排查

### 问题 1：规则不生效

**原因：** 可能未保存或文件格式错误

**解决：**
1. 检查 `default_rules.json` 文件是否存在
2. 使用 JSON 校验工具检查格式是否正确
3. 确保点击了"保存"按钮

### 问题 2：CSV 导入失败

**原因：** 文件编码或格式问题

**解决：**
1. 确保 CSV 文件使用 UTF-8 编码保存
2. 检查是否保留了表头行
3. 确认每行数据列数正确（别名2列，重命名2列，性别3列）

### 问题 3：在线更新连接失败

**原因：** 网络问题或服务器未配置

**解决：**
1. 检查网络连接
2. 确认服务器 URL 配置正确
3. 如不需要在线更新功能，可忽略此按钮

## 扩展开发

### 添加新的规则类型

1. 在 `default_rules.json` 中添加新字段
2. 在 `rule_manager.py` 中更新 `load_rules()` 和 `save_rules()` 方法
3. 在 `settings_dialog.py` 中添加新的标签页和处理逻辑

### 集成机器学习

未来可以集成机器学习模型：

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class MLMatcher:
    def train(self, excel_items):
        """使用 Excel 项目训练模型"""
        self.vectorizer = TfidfVectorizer()
        self.vectors = self.vectorizer.fit_transform(excel_items)
        self.items = excel_items
    
    def match(self, ocr_text, threshold=0.8):
        """使用模型匹配"""
        ocr_vector = self.vectorizer.transform([ocr_text])
        similarities = cosine_similarity(ocr_vector, self.vectors)[0]
        best_idx = similarities.argmax()
        
        if similarities[best_idx] >= threshold:
            return self.items[best_idx]
        return None
```

## 总结

新的规则管理系统提供了以下优势：

1. **灵活性**：支持多种规则管理方式
2. **可维护性**：无需修改代码即可更新规则
3. **扩展性**：易于添加新的规则类型和功能
4. **用户友好**：提供图形界面和 CSV 导入导出
5. **团队协作**：支持规则共享和在线更新

对于您提到的"匹配体检项目"需求，建议：
- **短期**：完善现有规则库，覆盖常见项目
- **中期**：使用智能模糊匹配减少规则数量
- **长期**：考虑引入机器学习模型自动学习匹配模式

