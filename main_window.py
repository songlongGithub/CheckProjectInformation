# 文件名: main_window.py
import os
import time
from typing import Optional

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTableWidget, QTableWidgetItem, QLabel,
                             QFileDialog, QMessageBox, QAbstractItemView, QHeaderView,
                             QDialog, QDialogButtonBox, QScrollArea, QSizePolicy,
                             QPlainTextEdit, QStyledItemDelegate)
from PyQt6.QtCore import QSettings, QThreadPool, Qt
from PyQt6.QtGui import QColor, QPixmap, QTextOption

from settings_dialog import SettingsDialog
from excel_parser import MedicalExamParser
from workers import Worker
import logic
from styles import MODERN_STYLE, STATUS_COLORS, EDITABLE_TABLE_STYLE

STATUS_ICON = {
    "ready": "⚪", "processing": "⏳", "matched_perfect": "✅",
    "matched_imperfect": "⚠️", "unmatched": "❌", "error": "❗"
}


class ClickableLabel(QLabel):
    """Lightweight QLabel that emits a callback on click."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._click_handler = None

    def set_click_handler(self, handler):
        self._click_handler = handler

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._click_handler:
            self._click_handler()
        super().mousePressEvent(event)


class ImagePreviewDialog(QDialog):
    """Dialog that displays a larger version of the OCR image."""

    def __init__(self, image_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("图片放大预览")
        self.setModal(True)
        self.setMinimumSize(600, 450)
        layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_area.setWidget(self.image_label)

        layout.addWidget(scroll_area)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        close_box.accepted.connect(self.accept)
        layout.addWidget(close_box)

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.image_label.setText("无法加载图片")
            return

        screen = self.screen() or (parent.windowHandle().screen() if parent and parent.windowHandle() else None)
        if screen:
            available = screen.availableGeometry()
            target_width = int(available.width() * 0.8)
            target_height = int(available.height() * 0.8)
            scaled = pixmap.scaled(target_width, target_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setPixmap(pixmap)


class ExpandingTextDelegate(QStyledItemDelegate):
    """Provide a spacious multi-line editor for table cells when copying text."""

    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        return editor

    def setEditorData(self, editor: QPlainTextEdit, index):
        editor.setPlainText(index.data() or "")
        editor.selectAll()

    def setModelData(self, editor: QPlainTextEdit, model, index):
        model.setData(index, editor.toPlainText())

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
        doc = editor.document()
        contents_width = max(option.rect.width() - editor.contentsMargins().left() - editor.contentsMargins().right(), 50)
        doc.setTextWidth(contents_width)
        frame = editor.frameWidth() * 2
        height = int(doc.size().height()) + editor.contentsMargins().top() + editor.contentsMargins().bottom() + frame
        height = max(height, option.rect.height())
        editor.setFixedHeight(height)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("体检方案智能核对工具 v2.7 (楠楠专用)")
        self.setGeometry(100, 100, 1200, 700)
        self.setStyleSheet(MODERN_STYLE)

        self.settings = QSettings("MyCompany", "MedicalExamChecker")
        self.thread_pool = QThreadPool()
        self.excel_path = None
        self.image_paths = []
        self.excel_data = {}
        self.excel_sheet_order = []
        self.comparison_results = {}
        self.scheme_to_row_map = {}
        self._current_image_path = None
        self.init_ui()
        self.update_rules_label()

    def init_ui(self):
        toolbar_layout = QHBoxLayout(); toolbar_layout.setSpacing(10); toolbar_layout.setContentsMargins(15, 15, 15, 10)
        btn_load_excel = QPushButton("① 加载Excel方案"); btn_load_excel.clicked.connect(self.load_excel)
        btn_load_images = QPushButton("② 加载图片"); btn_load_images.clicked.connect(self.load_images)
        btn_start = QPushButton("③ 开始自动匹配与对比"); btn_start.clicked.connect(self.start_processing)
        btn_settings = QPushButton("⚙️ 设置"); btn_settings.setObjectName("settingsButton"); btn_settings.clicked.connect(self.open_settings)
        self.rules_label = QLabel("规则已内置 | 点击'设置'按钮编辑"); self.rules_label.setObjectName("rulesLabel")
        self.status_label = QLabel("状态: 准备就绪"); self.status_label.setObjectName("statusLabel")
        toolbar_layout.addWidget(btn_load_excel); toolbar_layout.addWidget(btn_load_images); toolbar_layout.addWidget(btn_start)
        toolbar_layout.addStretch(); toolbar_layout.addWidget(self.rules_label); toolbar_layout.addWidget(btn_settings)
        main_layout = QHBoxLayout(); main_layout.setSpacing(15); main_layout.setContentsMargins(15, 10, 15, 10)
        left_panel = QVBoxLayout(); left_panel.setSpacing(10)
        left_title = QLabel("📋 自动匹配结果 (按Excel Sheet顺序)"); left_title.setObjectName("titleLabel"); left_panel.addWidget(left_title)
        self.results_table = QTableWidget(); self.results_table.setColumnCount(4); self.results_table.setHorizontalHeaderLabels(["匹配方案 (Excel)", "匹配图片 (OCR)", "状态", "统计"])
        header = self.results_table.horizontalHeader(); header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.verticalHeader().setVisible(False); self.results_table.setAlternatingRowColors(True)
        self.results_table.itemSelectionChanged.connect(self.display_comparison_details); left_panel.addWidget(self.results_table)
        right_panel = QVBoxLayout(); right_panel.setSpacing(10)
        self.detail_label = QLabel("📊 对比详情"); self.detail_label.setObjectName("titleLabel"); right_panel.addWidget(self.detail_label)
        legend_label = QLabel("✅ 完全匹配 | 🔵 别名/规则匹配 | ❌ 缺失项 | ⚠️ 多余项")
        legend_label.setStyleSheet("QLabel { background-color: #E8F5E9; padding: 5px 10px; border-radius: 4px; color: #2E7D32; font-size: 12px; }")
        right_panel.addWidget(legend_label)
        self.detail_table = QTableWidget(); self.detail_table.setColumnCount(2); self.detail_table.setHorizontalHeaderLabels(["表格标准项 (Excel)", "图片识别项 (OCR)"])
        self.detail_table.verticalHeader().setVisible(False); self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.detail_table.setAlternatingRowColors(True)
        self.detail_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.detail_table.verticalHeader().setDefaultSectionSize(38)
        self.detail_table.setStyleSheet(EDITABLE_TABLE_STYLE)
        self.detail_table.setItemDelegate(ExpandingTextDelegate(self.detail_table))
        right_panel.addWidget(self.detail_table)
        self.detail_image_label = ClickableLabel("🖼️ 图片预览"); self.detail_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_image_label.setStyleSheet("QLabel { border: 1px dashed #B0BEC5; color: #607D8B; padding: 12px; }")
        self.detail_image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.detail_image_label.setFixedHeight(180)
        self.detail_image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detail_image_label.set_click_handler(self.open_image_preview_dialog)
        right_panel.addWidget(self.detail_image_label)
        main_layout.addLayout(left_panel, 1); main_layout.addLayout(right_panel, 1)
        central_widget = QWidget(); root_layout = QVBoxLayout(central_widget); root_layout.setSpacing(0); root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(toolbar_layout); root_layout.addLayout(main_layout); root_layout.addWidget(self.status_label)
        root_layout.setContentsMargins(0, 0, 0, 15); self.setCentralWidget(central_widget)

    def open_settings(self): dialog = SettingsDialog(self); dialog.exec()
    def update_rules_label(self): self.rules_label.setText("规则已内置 | 点击 '设置' 按钮进行编辑")
    def update_status(self, message: str, status_type: str = "ready"):
        icons = {"ready": "⚪", "processing": "⏳", "success": "✅", "warning": "⚠️", "error": "❌"}
        icon = icons.get(status_type, "ℹ️")
        self.status_label.setText(f"{icon} {message}")
        if status_type in STATUS_COLORS:
            color = STATUS_COLORS[status_type]
            self.status_label.setStyleSheet(f"QLabel#statusLabel {{ border: 2px solid {color}; color: {color}; font-weight: bold; padding: 10px 15px; background-color: white; border-radius: 4px; }}")

    def load_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择Excel方案文件", "", "Excel Files (*.xlsx *.xls)")
        if not path: return
        self.excel_path = path
        try:
            parser = MedicalExamParser(self.excel_path)
            parser.build_rename_map(self.settings.value("rules/renames", []))
            parser.read_excel_data()
            self.excel_sheet_order = parser.sheet_names_in_order
            categorized_data_rich = parser.categorize_projects_by_gender_and_marital_status()
            parser.build_gender_rename_map(self.settings.value("rules/gender_renames", []))
            parser._apply_gender_renames(categorized_data_rich)
            simple_data = {}
            for scheme_name, categories in categorized_data_rich.items():
                simple_data[scheme_name] = {}
                for category_name, projects in categories.items():
                    unique_project_list = list({p['full_name']: p for p in projects}.values())
                    sorted_projects = sorted(unique_project_list, key=lambda x: x['row_index'])
                    simple_data[scheme_name][category_name] = [p['full_name'] for p in sorted_projects]
            self.excel_data = simple_data
            print("Log: Excel scheme combinations and items:")
            for scheme_name, categories in self.excel_data.items():
                for category_name, items in categories.items():
                    print(f"Log:   -> {scheme_name} - {category_name} ({len(items)} 项)")
                    for item in items:
                        print(f"Log:        • {item}")
            self.populate_scheme_table()
            self.update_status(f"已加载Excel '{os.path.basename(path)}' 并解析出 {self.results_table.rowCount()} 个方案", "success")
        except Exception as e:
            QMessageBox.critical(self, "Excel解析错误", f"解析Excel文件时发生错误:\n{e}"); self.excel_path = None

    def populate_scheme_table(self):
        self.results_table.setRowCount(0)
        self.scheme_to_row_map.clear()
        full_scheme_names = []
        for sheet_name in self.excel_sheet_order:
            categories = self.excel_data.get(sheet_name, {})
            for category in ['男', '女未婚', '女已婚']:
                if categories.get(category):
                    full_scheme_names.append(f"{sheet_name} - {category}")
        self.results_table.setRowCount(len(full_scheme_names))
        self.base_scheme_row_count = len(full_scheme_names)
        for i, name in enumerate(full_scheme_names):
            self.results_table.setItem(i, 0, QTableWidgetItem(name))
            self.results_table.setItem(i, 2, QTableWidgetItem(STATUS_ICON["ready"]))
            self.scheme_to_row_map[name] = i
        if full_scheme_names:
            print("Log: Excel schemes recognized:")
            for name in full_scheme_names:
                print(f"Log:   -> {name}")

    def load_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择图片文件", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if paths:
            self.image_paths = paths; self.update_status(f"已加载 {len(paths)} 张图片", "success")

    def start_processing(self):
        if not self.excel_path or not self.image_paths: return
        api_key = self.settings.value("ocr/api_key", type=str)
        secret_key = self.settings.value("ocr/secret_key", type=str)
        if not api_key or not secret_key:
            QMessageBox.warning(self, "缺少配置", "请在'设置'中配置百度OCR的API Key和Secret Key."); return
        base_rows = getattr(self, "base_scheme_row_count", self.results_table.rowCount())
        while self.results_table.rowCount() > base_rows:
            self.results_table.removeRow(self.results_table.rowCount() - 1)
        self.comparison_results.clear(); self.detail_table.setRowCount(0); self.detail_label.setText("对比详情:"); self.show_image_preview(None)
        for i in range(self.results_table.rowCount()):
            self.results_table.setItem(i, 1, QTableWidgetItem("")); self.results_table.setItem(i, 2, QTableWidgetItem(STATUS_ICON["ready"])); self.results_table.setItem(i, 3, QTableWidgetItem(""))
        worker = Worker(self.processing_thread, self.image_paths, self.settings, self.excel_data, self.scheme_to_row_map)
        worker.signals.progress.connect(self.update_result_row)
        worker.signals.finished.connect(self.processing_finished)
        worker.signals.error.connect(self.processing_error)
        self.thread_pool.start(worker); self.update_status("处理中... (0/{})".format(len(self.image_paths)), "processing")
    
    def display_comparison_details(self):
        selected_rows = self.results_table.selectionModel().selectedRows()
        if not selected_rows: return
        selected_row = selected_rows[0].row()
        result = self.comparison_results.get(selected_row)
        if not result:
            self.detail_table.setRowCount(0); self.detail_label.setText("📊 对比详情 (无匹配项)")
            self.show_image_preview(None)
            return
        status = result.get("status")
        display_title = result.get('ocr_title', result.get('image_name', ''))
        if status in ["matched_perfect", "matched_imperfect"]:
            self.detail_label.setText(f"📊 对比详情: \"{display_title}\" ↔️ \"{result['matched_sheet']}\"")
            comparison_report = result["comparison"]
            status_priority = {"匹配": 0, "缺失": 1, "多余": 2}
            ordered_report = sorted(
                comparison_report,
                key=lambda item: (status_priority.get(item["status"], 99))
            )
            self.detail_table.setRowCount(len(ordered_report))
            for row_index, report_item in enumerate(ordered_report):
                excel_text, ocr_text, status_item = report_item['excel_item'], report_item['ocr_item'], report_item['status']
                prefix, bg_color, text_color = "", None, QColor(0, 0, 0)
                if status_item == '匹配':
                    match_type = report_item.get('match_type')
                    if match_type == 'alias': prefix, bg_color, text_color = "🔵 ", QColor(173, 216, 230), QColor(0, 51, 102)
                    else: prefix, bg_color, text_color = "✅ ", QColor(144, 238, 144), QColor(0, 100, 0)
                elif status_item == '缺失': prefix, bg_color, text_color = "❌ ", QColor(255, 182, 193), QColor(139, 0, 0)
                elif status_item == '多余': prefix, bg_color, text_color = "⚠️ ", QColor(255, 228, 181), QColor(184, 134, 11)
                item_excel, item_ocr = QTableWidgetItem(prefix + excel_text), QTableWidgetItem(prefix + ocr_text)
                if bg_color:
                    item_excel.setBackground(bg_color); item_ocr.setBackground(bg_color)
                    item_excel.setForeground(text_color); item_ocr.setForeground(text_color)
                self.detail_table.setItem(row_index, 0, item_excel); self.detail_table.setItem(row_index, 1, item_ocr)
            self.show_image_preview(result.get("image_path"))
        elif status == "unmatched":
            self.detail_label.setText(f"📊 对比详情: OCR多余方案 \"{display_title}\"")
            extra_items = result.get("extra_items", [])
            self.detail_table.setRowCount(len(extra_items))
            for row_index, item in enumerate(extra_items):
                placeholder = QTableWidgetItem("【多余】")
                ocr_item = QTableWidgetItem(f"⚠️ {item}")
                self.detail_table.setItem(row_index, 0, placeholder); self.detail_table.setItem(row_index, 1, ocr_item)
            self.show_image_preview(result.get("image_path"))
        elif status == "error":
            message = result.get("message", "OCR请求失败")
            self.detail_label.setText(f"📊 对比详情: OCR失败 \"{display_title}\"")
            self.detail_table.setRowCount(1)
            self.detail_table.setItem(0, 0, QTableWidgetItem("【错误】"))
            self.detail_table.setItem(0, 1, QTableWidgetItem(f"❗ {message}"))
            self.show_image_preview(result.get("image_path"))
        else:
            self.detail_table.setRowCount(0); self.detail_label.setText("📊 对比详情 (无匹配项)")
            self.show_image_preview(None)

    def update_result_row(self, progress_data: dict):
        row = progress_data.get("row")
        status = progress_data["status"]
        if row is None:
            if status == "progress_update":
                current = progress_data.get("current_image", 0)
                total = progress_data.get("total_images", 0)
                image_name = progress_data.get("image_name", "")
                detail = f" - {image_name}" if image_name else ""
                self.update_status(f"处理中... ({current}/{total}){detail}", "processing")
                return
            if status == "unmatched":
                new_row = self.results_table.rowCount()
                self.results_table.insertRow(new_row)
                self.results_table.setItem(new_row, 0, QTableWidgetItem("【多余】OCR方案"))
                ocr_title = progress_data.get("ocr_title", "N/A")
                self.results_table.setItem(new_row, 1, QTableWidgetItem(ocr_title))
                self.results_table.setItem(new_row, 2, QTableWidgetItem(STATUS_ICON[status]))
                extra_items = progress_data.get("extra_items", [])
                stats_str = f"项目数:{len(extra_items)}"
                self.results_table.setItem(new_row, 3, QTableWidgetItem(stats_str))
                self.comparison_results[new_row] = {
                    "status": "unmatched",
                    "image_name": progress_data.get("image_name"),
                    "ocr_title": ocr_title,
                    "extra_items": extra_items,
                    "image_path": progress_data.get("image_path")
                }
                return
            if status == "error":
                new_row = self.results_table.rowCount()
                self.results_table.insertRow(new_row)
                self.results_table.setItem(new_row, 0, QTableWidgetItem("【失败】OCR方案"))
                ocr_title = progress_data.get("ocr_title", "N/A")
                self.results_table.setItem(new_row, 1, QTableWidgetItem(ocr_title))
                self.results_table.setItem(new_row, 2, QTableWidgetItem(STATUS_ICON[status]))
                message = progress_data.get("message", "OCR请求失败")
                self.results_table.setItem(new_row, 3, QTableWidgetItem(message))
                self.comparison_results[new_row] = {
                    "status": "error",
                    "image_name": progress_data.get("image_name"),
                    "ocr_title": ocr_title,
                    "message": message,
                    "image_path": progress_data.get("image_path")
                }
                return
            return
        self.results_table.setItem(row, 2, QTableWidgetItem(STATUS_ICON[status]))
        ocr_title = progress_data.get("ocr_title", "N/A")
        self.results_table.setItem(row, 1, QTableWidgetItem(ocr_title))
        if status in ["matched_perfect", "matched_imperfect"]:
            stats = progress_data["stats"]
            stats_str = f"匹配:{stats['matched']} 缺失:{stats['missing']} 多余:{stats['extra']}"
            self.results_table.setItem(row, 3, QTableWidgetItem(stats_str))
        elif status == "error":
            message = progress_data.get("message", "未知错误")
            self.results_table.setItem(row, 3, QTableWidgetItem(message))
            self.comparison_results[row] = {
                "status": "error",
                "image_name": progress_data.get("image_name"),
                "ocr_title": ocr_title,
                "message": message,
                "image_path": progress_data.get("image_path")
            }

    def processing_finished(self, results):
        if isinstance(results, dict):
            self.comparison_results.update(results)
        matched_images = {res.get('image_name') for res in self.comparison_results.values() if res and res.get("status") in ["matched_perfect", "matched_imperfect"]}
        matched_schemes_count = sum(1 for res in self.comparison_results.values() if res and res.get("status") in ["matched_perfect", "matched_imperfect"])
        processed_images_count = len({res.get('image_name') for res in self.comparison_results.values() if res})
        extra_count = sum(1 for res in self.comparison_results.values() if res and res.get("status") == "unmatched")
        error_count = sum(1 for res in self.comparison_results.values() if res and res.get("status") == "error")
        unmatched_images_count = max(len(self.image_paths) - len(matched_images) - error_count, 0)
        status_msg = f"已处理 {processed_images_count} 张图片，匹配 {matched_schemes_count} 个方案"
        if extra_count:
            status_msg += f"，另有 {extra_count} 个OCR方案未匹配"
        if error_count:
            status_msg += f"，{error_count} 个OCR请求失败"
        warning_needed = bool(unmatched_images_count or extra_count or error_count)
        self.update_status(status_msg, "warning" if warning_needed else "success")
        QMessageBox.information(self, "完成",
            f"所有图片均已处理完毕。\n\n✅ 已处理 {processed_images_count} 张图片\n✅ 成功匹配 {matched_schemes_count} 个方案\n⚠️ OCR 额外方案 {extra_count} 个\n❗ OCR 失败 {error_count} 个")

    def show_image_preview(self, image_path: Optional[str]):
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._current_image_path = image_path
                scaled = pixmap.scaled(self.detail_image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.detail_image_label.setPixmap(scaled)
                self.detail_image_label.setText("")
                return
        self._current_image_path = None
        self.detail_image_label.setPixmap(QPixmap())
        self.detail_image_label.setText("🖼️ 图片预览")

    def open_image_preview_dialog(self):
        if not self._current_image_path or not os.path.exists(self._current_image_path):
            return
        dialog = ImagePreviewDialog(self._current_image_path, self)
        dialog.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_image_path:
            self.show_image_preview(self._current_image_path)

    def processing_error(self, error_message: str):
        self.update_status(f"出现错误: {error_message}", "error"); QMessageBox.critical(self, "错误", f"处理过程中发生错误:\n{error_message}")

    @staticmethod
    def processing_thread(image_paths, settings, excel_data, scheme_to_row_map, progress_callback):
        alias_data = settings.value("rules/aliases", []); alias_map = logic.build_alias_map(alias_data)
        api_key = settings.value("ocr/api_key", type=str); secret_key = settings.value("ocr/secret_key", type=str)
        full_scheme_names = list(scheme_to_row_map.keys())
        access_token = logic.get_baidu_ocr_access_token(api_key, secret_key)
        if not access_token: raise Exception("获取百度OCR Access Token失败，请检查API密钥。")
        final_results = {}
        total_images = len(image_paths)
        for index, img_path in enumerate(image_paths):
            progress_callback.emit({
                "row": None,
                "status": "progress_update",
                "current_image": index + 1,
                "total_images": total_images,
                "image_name": os.path.basename(img_path),
                "image_path": img_path
            })
            ocr_json = logic.get_ocr_result_from_baidu(access_token, img_path)
            if not ocr_json:
                progress_callback.emit({
                    "row": None,
                    "status": "error",
                    "ocr_title": os.path.basename(img_path),
                    "message": "OCR请求失败，未获取到响应。",
                    "image_name": os.path.basename(img_path),
                    "image_path": img_path
                })
                continue
            words_result = ocr_json.get("words_result")
            if not words_result:
                error_message = ocr_json.get("error_msg") or "OCR未返回可用的识别结果。"
                progress_callback.emit({
                    "row": None,
                    "status": "error",
                    "ocr_title": os.path.basename(img_path),
                    "message": error_message,
                    "image_name": os.path.basename(img_path),
                    "image_path": img_path
                })
                continue
            schemes = logic.extract_data_from_ocr_json(ocr_json)
            if not schemes:
                progress_callback.emit({
                    "row": None,
                    "status": "error",
                    "ocr_title": os.path.basename(img_path),
                    "message": "OCR未识别到方案标题或项目。",
                    "image_name": os.path.basename(img_path),
                    "image_path": img_path
                })
                continue
            for ocr_title, ocr_items in schemes:
                display_title = ocr_title if ocr_title else f"[{os.path.basename(img_path)}]"
                matched_full_scheme = logic.find_best_match(ocr_title, full_scheme_names)
                if not matched_full_scheme:
                    progress_callback.emit({
                        "row": None,
                        "status": "unmatched",
                        "ocr_title": display_title,
                        "extra_items": ocr_items,
                        "image_name": os.path.basename(img_path),
                        "image_path": img_path
                    })
                    continue
                row_to_update = scheme_to_row_map.get(matched_full_scheme)
                if row_to_update is None: continue
                progress_callback.emit({"row": row_to_update, "status": "processing", "ocr_title": display_title})
                parts = matched_full_scheme.split(' - ');
                if len(parts) != 2: continue
                matched_sheet, sub_category = parts[0], parts[1]
                excel_items = excel_data.get(matched_sheet, {}).get(sub_category, [])
                comparison = logic.generate_comparison_report(excel_items, ocr_items, alias_map)
                stats = {"matched": sum(1 for i in comparison if i['status'] == '匹配'), "missing": sum(1 for i in comparison if i['status'] == '缺失'), "extra": sum(1 for i in comparison if i['status'] == '多余')}
                final_status = "matched_perfect" if stats['missing'] == 0 and stats['extra'] == 0 else "matched_imperfect"
                progress_callback.emit({"row": row_to_update, "status": final_status, "stats": stats, "ocr_title": display_title})
                final_results[row_to_update] = {
                    "status": final_status,
                    "image_name": os.path.basename(img_path),
                    "image_path": img_path,
                    "ocr_title": display_title,
                    "matched_sheet": matched_full_scheme,
                    "comparison": comparison
                }
                time.sleep(0.05)
        return final_results
