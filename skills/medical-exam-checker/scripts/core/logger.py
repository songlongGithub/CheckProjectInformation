# -*- coding: utf-8 -*-
"""统一日志配置。

日志格式：[Level][Module:Method] Message
所有模块通过 get_logger(__name__) 获得 logger 实例。
"""

import logging
import sys


# 全局标记，避免重复配置 handler
_CONFIGURED = False


class _BracketFormatter(logging.Formatter):
    """自定义格式化器：[Level][Module:Method] Message"""

    def format(self, record: logging.LogRecord) -> str:
        module_name = record.name
        method_name = record.funcName
        return f"[{record.levelname}][{module_name}:{method_name}] {record.getMessage()}"


def configure_logging(level: int = logging.INFO) -> None:
    """初始化根 logger。重复调用安全。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_BracketFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # 清理外部库默认 handler，防止格式混乱
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取 logger。首次调用前若未配置，则使用默认 INFO 级别。"""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
