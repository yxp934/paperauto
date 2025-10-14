"""
辅助工具函数模块
提供文件操作、JSON处理等通用功能
"""
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict


def save_json(data: Dict[str, Any], file_path: str) -> bool:
    """
    保存数据为JSON文件

    Args:
        data: 要保存的数据
        file_path: 文件路径

    Returns:
        bool: 是否成功
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"保存JSON失败: {e}")
        return False


def load_json(file_path: str) -> Dict[str, Any]:
    """
    从JSON文件加载数据

    Args:
        file_path: 文件路径

    Returns:
        Dict[str, Any]: 加载的数据
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON失败: {e}")
        return {}


def clean_temp_files(temp_dir: str) -> bool:
    """
    清理临时文件目录

    Args:
        temp_dir: 临时目录路径

    Returns:
        bool: 是否成功
    """
    try:
        path = Path(temp_dir)
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"清理临时文件失败: {e}")
        return False


def ensure_dir(directory: str) -> Path:
    """
    确保目录存在

    Args:
        directory: 目录路径

    Returns:
        Path: 目录Path对象
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_env_from_file(filepath: str = ".env") -> None:
    """
    轻量加载 .env 配置到 os.environ（无第三方依赖）
    - 忽略以 # 开头的注释行
    - 仅解析 KEY=VALUE 形式（不支持引号展开/转义）
    """
    try:
        p = Path(filepath)
        if not p.exists():
            return
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key and val and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"加载 .env 失败: {e}")

