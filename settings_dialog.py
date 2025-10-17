# 文件名: settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QDialogButtonBox, QHBoxLayout,
    QAbstractItemView, QHeaderView, QLabel, QGroupBox
)
from PyQt6.QtCore import QSettings
from typing import Any, List

# 从项目样式文件导入全局样式（确保项目存在 styles.py 且包含 MODERN_STYLE）
try:
    from styles import MODERN_STYLE, EDITABLE_TABLE_STYLE
except Exception:
    MODERN_STYLE = ""  # 兜底，避免样式文件缺失导致报错
    EDITABLE_TABLE_STYLE = ""


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 规则设置")
        self.setMinimumSize(750, 500)

        # 应用样式（若 styles.py 缺失，上面已兜底为空串）
        self.setStyleSheet(MODERN_STYLE)

        # 偏好存储
        self.settings = QSettings("MyCompany", "MedicalExamChecker")

        # === 单一根布局 ===
        root = QVBoxLayout(self)

        # === OCR Key 分组 ===
        ocr_group = QGroupBox("百度 OCR 配置")
        ocr_form = QFormLayout(ocr_group)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("在此输入百度 OCR 的 API Key")

        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setPlaceholderText("在此输入百度 OCR 的 Secret Key")
        self.secret_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # 载入已有配置（显式指定 type，避免返回 QVariant 类型）
        self.api_key_edit.setText(self.settings.value("ocr/api_key", "", str))
        self.secret_key_edit.setText(self.settings.value("ocr/secret_key", "", str))

        ocr_form.addRow("API Key：", self.api_key_edit)
        ocr_form.addRow("Secret Key：", self.secret_key_edit)
        root.addWidget(ocr_group)

        # === 规则 Tab ===
        self.tabs = QTabWidget(self)
        self.alias_tab = QWidget()
        self.rename_tab = QWidget()
        self.gender_tab = QWidget()

        # 按顺序添加标签页
        self.tabs.addTab(self.rename_tab, "表格重命名/拆分规则")
        self.tabs.addTab(self.gender_tab, "表格性别特定规则")
        self.tabs.addTab(self.alias_tab, "对比别名/同义词规则")

        # 构建各标签页内容
        self.setup_alias_tab()
        self.setup_rename_tab()
        self.setup_gender_tab()

        root.addWidget(self.tabs)

        # === 底部按钮 ===
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)

        root.addWidget(button_box)

        # === 加载规则数据 ===
        self.load_settings()

    # ---------- UI 片段 ----------
    def create_table_view(self, headers: List[str], parent_layout: QVBoxLayout) -> QTableWidget:
        """创建表格视图组件"""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)  # 交替行颜色
        table.verticalHeader().setDefaultSectionSize(42)
        table.setStyleSheet(EDITABLE_TABLE_STYLE)

        # 按钮布局
        add_button = QPushButton("➕ 添加行")
        add_button.setObjectName("secondaryButton")
        add_button.setToolTip("在表格末尾添加新行")

        del_button = QPushButton("➖ 删除选中行")
        del_button.setObjectName("secondaryButton")
        del_button.setToolTip("删除当前选中的行")

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        button_layout.addWidget(add_button)
        button_layout.addWidget(del_button)

        parent_layout.addWidget(table)
        parent_layout.addLayout(button_layout)

        add_button.clicked.connect(lambda: table.insertRow(table.rowCount()))
        del_button.clicked.connect(lambda: self._safe_remove_current_row(table))

        return table

    def _safe_remove_current_row(self, table: QTableWidget):
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def setup_alias_tab(self):
        """设置对比别名规则标签页"""
        layout = QVBoxLayout(self.alias_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        info_label = QLabel("💡 用于在对比阶段将 OCR 识别的不规范名称映射到 Excel 标准名称")
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "color: #616161; padding: 5px; background-color: #E3F2FD; border-radius: 4px;"
        )
        layout.addWidget(info_label)

        self.alias_table = self.create_table_view(["别名 (OCR识别名)", "标准名 (Excel标准名)"], layout)

    def setup_rename_tab(self):
        """设置表格重命名规则标签页"""
        layout = QVBoxLayout(self.rename_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        info_label = QLabel("💡 在解析 Excel 阶段改写或拆分项目名称。支持 SELF 关键字表示保留原名")
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "color: #616161; padding: 5px; background-color: #FFF9C4; border-radius: 4px;"
        )
        layout.addWidget(info_label)

        self.rename_table = self.create_table_view(["原项目名", "新项目名 (多个用英文逗号 , 分隔)"], layout)

    def setup_gender_tab(self):
        """设置性别特定规则标签页"""
        layout = QVBoxLayout(self.gender_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        info_label = QLabel("💡 在解析 Excel 阶段，根据性别分类使用不同名称")
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "color: #616161; padding: 5px; background-color: #F3E5F5; border-radius: 4px;"
        )
        layout.addWidget(info_label)

        self.gender_table = self.create_table_view(["原项目名", "男性新名", "女性新名"], layout)

    # ---------- 数据加载/保存 ----------
    def load_settings(self):
        # 默认规则
        default_aliases = [
            ['静脉采血', '采血'],
            ['眼科常规', '眼科检查'],
            ['营养B餐', '标准早餐'],
            ['碳十三呼气检查', 'C13'],
            ['碳十四呼吸检测', 'C14'],
            ['乳腺彩超', '乳腺彩色超声'],
            ['女性盆腔彩超', '女性彩色盆腔超声'],
            ['男性盆腔彩超', '男性彩色盆腔超声'],
            ['常规心电图', '十二导联心电图'],
            ['腹部超声', '腹部彩色超声'],
            ['耳鼻喉常规', '耳鼻咽喉检查'],
            ['甲状腺彩超', '甲状腺彩色超声'],
            ['新女性肿瘤12项(H)', '新肿瘤12项女(H)'],
            ['新肿瘤12项男(H)', '新男性肿瘤12项(H)'],
            ['肺部CT', '胸部CT'],
            ['HPV-25', 'HPV多型检测'],
            ['血流变', '血流变(新)'],
            ['肝功全套', '肝功十三项'],
            ['肝功13项(A)', '肝功十三项'],
            ['女性七项肿瘤标志物(H)', '七项肿瘤标志物（女性）（H）'],
            ['男性八项肿瘤标志物(H)', '七项肿瘤标志物（男性）（H）'],
            ['血清胰岛素(INS)(A)', '血清胰岛素'],
            ['血清C测定(A)', '血清C肽测定'],
            ['动脉硬化', '全身动脉硬化检测'],
            ['宫颈涂片', '宫颈刮片'],
            ['胆红素三项', '胆红素组合(三项)'],
            ['空腹血糖(GLU)', '空腹血糖'],
            ['人体成份', '人体成分分析'],
            ['C-反应蛋白', '反应蛋白(CRP)'],
            ['载脂蛋白A', '载脂蛋白-A1'],
            ['心肌酶2项', '心肌酶两项'],
            ['肠癌检测', '居家便隐血检测（前台）'],
            ['碳十三呼气检查', 'C13呼气试验'],
            ['HPV多型检测', '七项肿瘤标志物(女性)(H)'],
            ['女性项肿瘤标志物(H)', '七项肿瘤标志物(女性)(H)'],
            ['HRA健康功能风险评估系统', 'HRA'],
            ['胃功能3项', '胃功能3项(H)'],
            ['胃泌素17', '胃泌素17(H)'],
        ]
        default_renames = [
            ['一般检查', '身高体重,血压,放射项目不出胶片,超声项目不出片'],
            ['妇科检查', 'SELF,白带常规'],
            ['裂隙灯、眼底', '眼底检查,裂隙灯'],
            ['肝功十一项', '肝功四项,胆红素组合(三项),蛋白组合(四项)'],
        ]
        default_gender_renames = [
            ['外科检查', '外科检查（男）', '外科检查（女）']
        ]

        # 兼容从 QSettings 读取为字符串/None 的情况
        aliases = self._ensure_defaults(
            "rules/aliases",
            self._load_list("rules/aliases", default_aliases),
            default_aliases,
        )
        renames = self._ensure_defaults(
            "rules/renames",
            self._load_list("rules/renames", default_renames),
            default_renames,
        )
        gender_renames = self._ensure_defaults(
            "rules/gender_renames",
            self._load_list("rules/gender_renames", default_gender_renames),
            default_gender_renames,
        )

        self.populate_table(self.alias_table, aliases)
        self.populate_table(self.rename_table, renames)
        self.populate_table(self.gender_table, gender_renames)

    def _load_list(self, key: str, default: List[List[str]]) -> List[List[str]]:
        """从 QSettings 读取列表；若为字符串/None，做容错处理"""
        val: Any = self.settings.value(key, None)
        if val is None:
            return default
        if isinstance(val, list):
            # 期望是 List[List[str]]；若是扁平或内部元素不是 list，尽量纠正
            if val and not isinstance(val[0], list):
                return [val]  # 退化为单行
            return val
        # 可能是字符串（某些环境下 QSettings 会序列化为 str）
        try:
            import json
            parsed = json.loads(val)
            if isinstance(parsed, list):
                if parsed and not isinstance(parsed[0], list):
                    return [parsed]
                return parsed
        except Exception:
            pass
        # 无法解析则返回默认
        return default

    def _ensure_defaults(
        self,
        key: str,
        current: List[List[str]],
        defaults: List[List[str]],
        key_index: int = 0,
    ) -> List[List[str]]:
        """Merge stored rules with new defaults so updates take effect."""
        if not current:
            merged = [list(row) for row in defaults]
            self.settings.setValue(key, merged)
            return merged

        existing_keys = {
            row[key_index]
            for row in current
            if isinstance(row, list) and len(row) > key_index
        }

        merged = [list(row) if isinstance(row, list) else [row] for row in current]
        appended = False
        for row in defaults:
            if not isinstance(row, list) or len(row) <= key_index:
                continue
            primary = row[key_index]
            if primary in existing_keys:
                continue
            merged.append(list(row))
            appended = True

        if appended:
            self.settings.setValue(key, merged)
        return merged

    def populate_table(self, table: QTableWidget, data: List[List[str]]):
        table.setRowCount(0)
        for row_data in data:
            row_position = table.rowCount()
            table.insertRow(row_position)
            for col_index, cell_data in enumerate(row_data):
                table.setItem(row_position, col_index, QTableWidgetItem(str(cell_data)))

    def save_settings(self):
        # 保存 OCR Key（去除首尾空格）
        self.settings.setValue("ocr/api_key", self.api_key_edit.text().strip())
        self.settings.setValue("ocr/secret_key", self.secret_key_edit.text().strip())

        # 保存规则（存为 Python 原生列表，QSettings 在本地序列化）
        self.settings.setValue("rules/aliases", self.get_table_data(self.alias_table))
        self.settings.setValue("rules/renames", self.get_table_data(self.rename_table))
        self.settings.setValue("rules/gender_renames", self.get_table_data(self.gender_table))

        self.accept()

    def get_table_data(self, table: QTableWidget) -> List[List[str]]:
        data: List[List[str]] = []
        for row in range(table.rowCount()):
            row_data: List[str] = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                row_data.append(item.text().strip() if item else "")
            data.append(row_data)
        return data
