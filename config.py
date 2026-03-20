#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 统一管理所有硬编码值
"""

import os
from pathlib import Path

# ==================== 路径配置 ====================
# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 数据库路径
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "database.db"
DEFAULT_CACHE_PATH = PROJECT_ROOT / "cache"

# 配置文件路径
COMPANIES_CONFIG_PATH = PROJECT_ROOT / "car_companies_config.json"
UNIVERSITIES_CONFIG_PATH = PROJECT_ROOT / "universities_config.json"

# ==================== 服务器配置 ====================
# Dashboard 服务器配置
DASHBOARD_PORT = 5006
DASHBOARD_ADDRESS = "localhost"
DASHBOARD_TITLE = "PaperMap Dashboard"

# App 服务器配置
APP_PORT = 5007
APP_ADDRESS = "0.0.0.0"  # 允许所有网络接口访问
APP_TITLE = "PaperMap"

# WebSocket 配置
WEBSOCKET_MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
WEBSOCKET_ALLOW_ORIGIN = ['*']

# ==================== 颜色配置 ====================
# 主题色 - PaperMap 风格：现代蓝色渐变
THEME_PRIMARY = "#2563eb"  # 更现代的蓝色
THEME_SECONDARY = "#1e40af"  # 深蓝色
THEME_GRADIENT_START = "#3b82f6"  # 亮蓝色
THEME_GRADIENT_END = "#1e40af"  # 深蓝色

# 链接颜色
LINK_COLOR = "#2563eb"  # 与主题色一致
LINK_COLOR_ALT = "#1d4ed8"  # 深蓝色

# 背景色
BG_COLOR_LIGHT = "#f8fafc"  # 更柔和的浅灰蓝
BG_COLOR_LIGHTER = "#f1f5f9"  # 浅灰蓝
BG_COLOR_WHITE = "#ffffff"

# 文本颜色
TEXT_COLOR_PRIMARY = "#1e293b"  # 深灰蓝
TEXT_COLOR_SECONDARY = "#64748b"  # 中灰蓝
TEXT_COLOR_WHITE = "#ffffff"

# 标签颜色
TAG_BG_COLOR = "#dbeafe"  # 浅蓝色
TAG_REMOVE_COLOR = "#dc2626"  # 红色

# 按钮颜色
BUTTON_PRIMARY_BG = "#2563eb"  # 主题蓝色
BUTTON_SUCCESS_BG = "#10b981"  # 绿色
BUTTON_WARNING_BG = "#f59e0b"  # 橙色
BUTTON_DANGER_BG = "#ef4444"  # 红色

# 边框颜色
BORDER_COLOR = "#e2e8f0"  # 浅灰蓝
BORDER_COLOR_PRIMARY = "#2563eb"  # 主题蓝色

# ==================== 尺寸配置 ====================
# 按钮尺寸
BUTTON_WIDTH_SMALL = 100
BUTTON_WIDTH_MEDIUM = 120
BUTTON_WIDTH_LARGE = 150
BUTTON_HEIGHT_DEFAULT = 32
BUTTON_HEIGHT_INPUT = 31

# 输入框尺寸
INPUT_WIDTH_DEFAULT = 300
INPUT_WIDTH_DATE = 120
INPUT_HEIGHT_DEFAULT = 31

# 表格尺寸
TABLE_HEIGHT_DEFAULT = 1000
TABLE_HEIGHT_MEDIUM = 700
TABLE_HEIGHT_SMALL = 400

# 面板尺寸
PANEL_WIDTH_DEFAULT = 400
PANEL_WIDTH_SMALL = 280
PANEL_HEIGHT_TITLE = 40

# 间距
SPACER_WIDTH_SMALL = 15
SPACER_WIDTH_MEDIUM = 20
SPACER_HEIGHT_SMALL = 10
SPACER_HEIGHT_MEDIUM = 20

# ==================== 延迟配置 ====================
# API 请求延迟（秒）
API_DELAY_SHORT = 1
API_DELAY_MEDIUM = 2
API_DELAY_LONG = 3

# ==================== 文本配置 ====================
# 按钮文本
BTN_TEXT_REFRESH = "🔄 刷新数据"
BTN_TEXT_COMPLETE = "⚙️ Complete"
BTN_TEXT_INSERT = "📥 Insert"
BTN_TEXT_ADD_TAG = "添加标签"
BTN_TEXT_CLOSE = "关闭"
BTN_TEXT_MANAGE_TAGS = "管理标签"

# 提示文本
MSG_NO_TAGS = "暂无标签"
MSG_NO_PAPERS = "暂无论文"
MSG_PLEASE_SEARCH = "请输入搜索关键词"
MSG_CLICK_TAG = "点击表格中的标签查看关联论文"
MSG_SELECT_TAG = "请选择标签查看关联论文"

# 标题文本
TITLE_MAIN = "🗺️ PaperMap"
TITLE_DASHBOARD = "PaperMap Dashboard"

# ==================== 样式配置 ====================
# 渐变背景 - PaperMap 风格
GRADIENT_PURPLE = f"linear-gradient(135deg, {THEME_GRADIENT_START} 0%, {THEME_GRADIENT_END} 100%)"
GRADIENT_BLUE = "linear-gradient(135deg, #3b82f6 0%, #1e40af 100%)"
GRADIENT_PINK = "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"

# 边框圆角 - 更现代的圆角
BORDER_RADIUS_SMALL = "4px"
BORDER_RADIUS_MEDIUM = "6px"
BORDER_RADIUS_LARGE = "8px"
BORDER_RADIUS_XLARGE = "12px"

# 字体大小
FONT_SIZE_SMALL = "12px"
FONT_SIZE_DEFAULT = "13px"
FONT_SIZE_MEDIUM = "14px"
FONT_SIZE_LARGE = "16px"
FONT_SIZE_TITLE = "28px"  # 更大的标题

# ==================== 其他配置 ====================
# 表格配置
TABLE_LAYOUT = "fit_columns"
TABLE_THEME = "bootstrap4"
TABLE_SHOW_INDEX = False

# 分页配置
PAGINATION_SIZE = 50

# 搜索配置
SEARCH_MIN_LENGTH = 1
SEARCH_DELAY = 300  # 毫秒

# 标签配置
TAG_SEPARATOR = "."
MAX_TAG_DEPTH = 10
# 从 arXiv comment 解析出的顶会标签前缀，完整标签形如 venue.NeurIPS（不含年份）
VENUE_TAG_PREFIX = "venue"

# ==================== 环境变量支持 ====================
# 允许通过环境变量覆盖配置
def get_db_path():
    """获取数据库路径，支持环境变量覆盖"""
    return os.getenv("DB_PATH", str(DEFAULT_DB_PATH))

def get_cache_path():
    """获取缓存路径，支持环境变量覆盖"""
    return os.getenv("CACHE_PATH", str(DEFAULT_CACHE_PATH))

def get_dashboard_port():
    """获取 Dashboard 端口，支持环境变量覆盖"""
    return int(os.getenv("DASHBOARD_PORT", DASHBOARD_PORT))

def get_app_port():
    """获取 App 端口，支持环境变量覆盖"""
    return int(os.getenv("APP_PORT", APP_PORT))

def get_dashboard_address():
    """获取 Dashboard 地址，支持环境变量覆盖"""
    return os.getenv("DASHBOARD_ADDRESS", DASHBOARD_ADDRESS)

def get_app_address():
    """获取 App 地址，支持环境变量覆盖"""
    return os.getenv("APP_ADDRESS", APP_ADDRESS)
