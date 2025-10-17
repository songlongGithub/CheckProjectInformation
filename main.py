# 文件名: main.py
import sys
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用信息，用于QSettings定位配置文件
    app.setOrganizationName("MyCompany")
    app.setApplicationName("MedicalExamChecker")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
