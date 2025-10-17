# 文件名: styles.py
"""
应用样式定义
"""

# 现代化的QSS样式表
MODERN_STYLE = """
/* 主窗口背景 */
QMainWindow {
    background-color: #f5f5f5;
}

/* 通用字体 */
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
}

/* 主要功能按钮样式（加载、开始等） */
QPushButton {
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    min-height: 35px;
}

QPushButton:hover {
    background-color: #1976D2;
}

QPushButton:pressed {
    background-color: #0D47A1;
}

QPushButton:disabled {
    background-color: #BDBDBD;
    color: #757575;
}

/* 次要功能按钮样式（添加、删除、保存、取消等） */
QPushButton#secondaryButton {
    min-height: 28px;
    padding: 6px 16px;
    font-size: 12px;
}

/* 设置按钮特殊样式 */
QPushButton#settingsButton {
    background-color: #FF9800;
    min-width: 80px;
}

QPushButton#settingsButton:hover {
    background-color: #F57C00;
}

/* 对话框按钮样式（保存、取消） */
QDialogButtonBox QPushButton {
    min-height: 30px;
    padding: 8px 20px;
}

/* 表格样式 */
QTableWidget {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    gridline-color: #EEEEEE;
    selection-background-color: #BBDEFB;
}

QTableWidget::item {
    padding: 8px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #BBDEFB;
    color: #000000;
}

QTableWidget::item:hover {
    background-color: #E3F2FD;
}

/* 表头样式 */
QHeaderView::section {
    background-color: #2196F3;
    color: white;
    padding: 10px;
    border: none;
    font-weight: bold;
    font-size: 13px;
}

QHeaderView::section:hover {
    background-color: #1976D2;
}

/* 标签样式 */
QLabel {
    color: #424242;
}

QLabel#titleLabel {
    font-size: 15px;
    font-weight: bold;
    color: #1976D2;
    padding: 5px;
}

QLabel#statusLabel {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 10px 15px;
    font-size: 13px;
}

QLabel#rulesLabel {
    color: #616161;
    padding: 5px 10px;
}

/* 分隔线样式 */
QFrame[frameShape="4"] {
    color: #E0E0E0;
}

/* 滚动条样式 */
QScrollBar:vertical {
    background: #F5F5F5;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #BDBDBD;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #9E9E9E;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #F5F5F5;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #BDBDBD;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #9E9E9E;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 对话框样式 */
QDialog {
    background-color: #f5f5f5;
}

/* Tab 控件样式 */
QTabWidget::pane {
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    background-color: white;
    top: -1px;
}

QTabBar::tab {
    background-color: #EEEEEE;
    color: #616161;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: white;
    color: #2196F3;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #E3F2FD;
}

/* 输入框样式 */
QLineEdit {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 8px;
    background-color: white;
}

QLineEdit:focus {
    border: 2px solid #2196F3;
}

/* 消息框样式 */
QMessageBox {
    background-color: white;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""

# 可编辑表格的统一样式
EDITABLE_TABLE_STYLE = (
    "QTableWidget::item { padding: 6px 10px; }"
    "QTableWidget QLineEdit { padding: 6px 8px; font-size: 14px; }"
    "QTableWidget QPlainTextEdit { padding: 6px 8px; font-size: 14px; }"
)

# 状态颜色定义
STATUS_COLORS = {
    "ready": "#757575",      # 灰色
    "processing": "#FF9800", # 橙色
    "success": "#4CAF50",    # 绿色
    "warning": "#FFC107",    # 黄色
    "error": "#F44336"       # 红色
}
