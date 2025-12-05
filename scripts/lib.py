#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperMap 脚本公共库
- 使用 pysqlite3（不可用时回退到 sqlite3）
- 提供 Database 实例与路径
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import pysqlite3 as sqlite3
except ImportError:
    import sqlite3

# 项目根目录（scripts/ 的上级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_db_path
from database import Database


def get_db() -> Database:
    """获取 Database 实例，使用 config.get_db_path() 或环境变量 DB_PATH"""
    return Database(get_db_path())


__all__ = ["get_db", "sqlite3", "PROJECT_ROOT", "get_db_path"]
