"""
日志工具模块
提供统一的日志记录接口
"""
import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取logger实例
    
    Args:
        name: logger名称
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
    
    Returns:
        logging.Logger: logger实例
    """
    logger = logging.getLogger(name)
    
    # 如果logger已经有handler，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    if level is None:
        import os
        level = os.getenv("LOG_LEVEL", "INFO")
    
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 创建控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logger.level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加handler
    logger.addHandler(console_handler)
    
    # 防止日志传播到root logger
    logger.propagate = False
    
    return logger

