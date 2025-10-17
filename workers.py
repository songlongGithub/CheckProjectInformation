# 文件名: workers.py
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

class WorkerSignals(QObject):
    """
    # 中文注释: 定义后台任务可发出的信号
    """
    finished = pyqtSignal(object)  # 任务完成信号，object是返回结果
    error = pyqtSignal(str)        # 任务出错信号，str是错误信息
    progress = pyqtSignal(dict)    # 任务进度更新信号，dict是进度信息

class Worker(QRunnable):
    """
    # 中文注释: 通用后台工作线程
    """
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            # 传递progress_callback给目标函数
            result = self.fn(*self.args, **self.kwargs, progress_callback=self.signals.progress)
        except Exception as e:
            self.signals.error.emit(str(e))
        else:
            self.signals.finished.emit(result)
