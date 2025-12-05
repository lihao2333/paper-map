# PaperMap Cursor Skills

本项目的 Cursor Agent Skill 内置于工程顶层，软链接整个工程到 Cursor 即可使用。

## 安装

将 paper-map 工程软链接到 Cursor skill 目录：

```bash
# 默认安装到 ~/.cursor/skills/
./skills/install_skills.sh

# 指定目标目录
./skills/install_skills.sh /path/to/skills

# 或通过环境变量
CURSOR_SKILLS_DIR=/path/to/skills ./skills/install_skills.sh
```

安装后：`<目标目录>/paper-map` → 本工程根目录。AI 可自动发现 `SKILL.md`，数据库 `data/database.db` 相对于工程根解析，软链接后路径仍正确。

## 当前 Skill

| Skill | 描述 |
|-------|------|
| paper-map | 查询 PaperMap SQLite 数据库，按公司/时间/作者/标签检索论文并生成总结 |

## 目录结构

```
paper-map/                 # 工程根目录（软链接目标）
├── SKILL.md               # Skill 定义（工程顶层）
├── scripts/
│   └── query_company.py   # 查询辅助脚本
├── data/
│   └── database.db
└── skills/
    ├── README.md          # 本文件
    └── install_skills.sh  # 安装脚本
```
