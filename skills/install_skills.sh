#!/usr/bin/env bash
# 将 paper-map 项目作为 skill 安装到指定目录（软链接整个工程）
# 用法: ./skills/install_skills.sh [目标目录]
# 或: CURSOR_SKILLS_DIR=/path/to/skills ./skills/install_skills.sh
# 默认目标: ~/.cursor/skills
#
# SKILL.md 在工程顶层，数据库路径 data/database.db 始终相对于工程根目录，软链接后仍正确解析
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${1:-${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}}"

mkdir -p "$TARGET_DIR"

# 软链接整个工程为 paper-map skill（SKILL.md 在工程根目录）
if [[ -f "$PROJECT_ROOT/SKILL.md" ]]; then
    echo "安装: paper-map -> $TARGET_DIR/paper-map (symlink)"
    rm -rf "$TARGET_DIR/paper-map"
    ln -sf "$PROJECT_ROOT" "$TARGET_DIR/paper-map"
    echo "安装完成。$TARGET_DIR/paper-map -> $PROJECT_ROOT（git pull 后自动更新）"
else
    echo "错误: 未找到 $PROJECT_ROOT/SKILL.md"
    exit 1
fi
