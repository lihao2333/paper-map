---
name: paper-map
description: Query and summarize paper data from PaperMap SQLite database. 支持按公司、高校、作者、标签、时间等维度检索论文，支持多公司对比、趋势分析、技术路线梳理、领域综述等。基本上所有与论文相关的需求（查某司/某校/某作者的论文、对比分析、主题统计、最新进展、技术路线等）都可用本 skill 完成。 
---

# SQLite 数据库查询与总结

本 skill 指导如何查询 PaperMap 的 SQLite 数据库，并按要求返回总结。

## 数据库路径

- 默认：`data/database.db`（相对于**工程根目录**）
- 工程根目录 = 本 SKILL 所在目录（安装后将 paper-map 软链到 `~/.cursor/skills/paper-map`）
- 可通过 `config.get_db_path()` 获取，或环境变量 `DB_PATH` 覆盖

## 数据库 Schema

### 表结构

| 表名 | 列名 | 类型 | 说明 |
|------|------|------|------|
| **paper** | paper_id | TEXT | 主键 |
| | arxiv_id | TEXT | 可选，唯一（格式 YYMM.NNNNN） |
| | paper_url | TEXT | 必填 |
| | date | TEXT | yyyyMM 格式 |
| | alias | TEXT | 短标题 |
| | full_name | TEXT | 完整标题 |
| | abstract | TEXT | 摘要 |
| | summary | TEXT | 总结 |
| **paper_company** | paper_id | TEXT | FK → paper |
| | company_name | TEXT | 公司名 |
| **paper_university** | paper_id | TEXT | FK → paper |
| | university_name | TEXT | 高校名 |
| **paper_author** | paper_id | TEXT | FK → paper |
| | author_name | TEXT | 作者名 |
| | author_order | INTEGER | 作者排序（一作、二作等） |
| **tag** | tag_id | INTEGER | 主键 |
| | tag_name | TEXT | 标签名，支持层级（如 自动驾驶.感知） |
| **paper_tag** | paper_id | TEXT | FK → paper |
| | tag_id | INTEGER | FK → tag |

### 视图 paper_based_view

聚合论文及其关联信息，常用列：

| 列名 | 说明 |
|------|------|
| paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary | 同 paper 表 |
| company_names | 逗号分隔的公司名 |
| university_names | 逗号分隔的高校名 |
| author_names | 按 author_order 排序的作者名，逗号分隔 |

### 格式约定

| 字段 | 格式 | 示例 |
|------|------|------|
| date | yyyyMM | 202401, 202412 |
| arxiv_id | YYMM.NNNNN | 2401.12345（可推 date: 202401） |
| company_names / university_names | 逗号分隔 | `Waymo, Google` |
| tag_name | 支持层级 | `自动驾驶.感知` |

### 关注公司 / 关注高校 配置表

| 表名 | 列名 | 说明 |
|------|------|------|
| **watched_company** | name | 显示名（如中文名） |
| | match_rule | 匹配规则，用于匹配 paper_company.company_name |
| **watched_university** | name | 显示名 |
| | match_rule | 匹配规则，用于匹配 paper_university.university_name |

**匹配规则格式**（从数据库获取，勿自行定义）：
- 精确匹配：不含通配符的字符串，对应 SQL `IN (?)`
- 通配符：`*` → `%`，`?` → `_`，对应 SQL `LIKE ?`

获取配置：`db.get_all_watched_companies()`、`db.get_all_watched_universities()`，返回 `[{"id", "name", "match_rule"}, ...]`。

## 公司/高校搜索约束（重要）

涉及**公司**或**高校**维度的搜索时，**必须只使用数据库中配置的关注公司/关注高校**：

1. **不得自行定义**匹配规则（如随意用 `LIKE '%Tesla%'`）
2. **必须先**从 `watched_company` / `watched_university` 表读取配置，用其 `match_rule` 构建查询
3. 用户提到的公司/高校名，需与 `name` 或 `match_rule` 对应：若不在关注列表中，应提示「该公司/高校不在关注列表中」或建议用户到设置中添加到关注列表

参考实现逻辑见 `database.py` 中 `get_car_company_paper_matrix()`、`get_university_paper_matrix()`。

## 基本查询模式

```python
import sqlite3
from config import get_db_path

db_path = get_db_path()
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row  # 支持列名访问
cursor = conn.cursor()
cursor.execute("SELECT * FROM paper_based_view WHERE ...")
rows = cursor.fetchall()
conn.close()
```

## 常用查询示例

### 1. 某关注公司某段时间的论文

公司名必须对应数据库中的关注公司。先读取 `watched_company`，找到用户提及公司对应的 match_rule，再构建查询：

```python
# 伪代码：先获取关注公司配置
watched = db.get_all_watched_companies()  # [{name, match_rule}, ...]
# 按 name 分组得到 match_rules 列表，再分离精确匹配与通配符，构建 SQL
# 精确：WHERE pc.company_name IN (?,?,...)
# 通配：WHERE pc.company_name LIKE ?
```

```sql
-- 示例：若 match_rule 为 "Tesla" 或 "Tesla*"（转 LIKE 'Tesla%'）
SELECT p.paper_id, p.alias, p.full_name, p.date, p.abstract, p.summary
FROM paper p
JOIN paper_company pc ON p.paper_id = pc.paper_id
WHERE (pc.company_name IN ('Tesla', 'Tesla Inc.') OR pc.company_name LIKE 'Tesla%')
  AND p.date >= '202401' AND p.date <= '202412'
ORDER BY p.date DESC;
```

### 2. 多关注公司对比（某时间段）

仅统计关注公司，从 `watched_company` 获取所有 match_rule，构建 IN/LIKE 条件后 GROUP BY。

### 3. 某关注高校 + 某标签

高校名必须对应数据库中的关注高校。先读取 `watched_university`，用 match_rule 构建条件（**LIKE/IN 的具体值必须来自数据库，勿写死**）：

```python
# 伪代码：与公司同理，从 get_all_watched_universities() 获取 match_rule 列表
# 按 match_rule 分离精确匹配与通配符，构建 WHERE 条件
```

```sql
-- 通过 paper_university 表查询（条件中的值来自 watched_university.match_rule）
SELECT * FROM paper_based_view
WHERE paper_id IN (
  SELECT paper_id FROM paper_university
  WHERE university_name IN (...) OR university_name LIKE ?  -- 由 watched_university 提供
)
AND paper_id IN (SELECT paper_id FROM paper_tag WHERE tag_id = (SELECT tag_id FROM tag WHERE tag_name = 'autonomous driving'));
```

### 4. 某作者近期工作

```sql
SELECT * FROM paper_based_view
WHERE author_names LIKE '%John Smith%'
  AND date >= '202401'
ORDER BY date DESC;
```

### 5. 按主题/标签统计

```sql
SELECT t.tag_name, COUNT(*) FROM paper_tag pt
JOIN tag t ON pt.tag_id = t.tag_id
JOIN paper p ON pt.paper_id = p.paper_id
WHERE p.date BETWEEN '202401' AND '202412'
GROUP BY t.tag_name
ORDER BY 2 DESC;
```

## 输出总结流程

当用户要求「某公司某段时间的工作内容」时：

1. **解析意图**：提取公司名、时间范围（支持 2024、2024Q1、202401-202412 等）
2. **执行查询**：用上述 SQL 获取论文列表
3. **生成总结**：按以下结构输出：

```markdown
# [公司名] [时间范围] 工作内容总结

## 概览
- 论文数量：N 篇
- 主要方向：[根据 abstract/summary 归纳]

## 重点论文
1. **[alias]** - 简要描述
   - 链接：paper_url
   - 摘要要点：...
2. ...

## 趋势与洞察
[基于多篇论文的共性总结]
```

## 更多应用场景

| 用户意图 | 查询要点 | 总结方式 |
|----------|----------|----------|
| 「特斯拉 2024 发了哪些论文」 | company + date | 列表 + 简短每篇要点 |
| 「Waymo 和 Cruise 谁发得多」 | 多 company 对比 | 数量统计 + 差异分析 |
| 「Stanford 自动驾驶方向的最新进展」 | university + tag | 领域综述式总结 |
| 「某作者最近在做什么」 | author + date | 研究方向演变 |
| 「2024 年 BEV 相关论文」 | tag + date | 技术趋势总结 |
| 「某公司技术路线」 | company + 多篇 abstract | 技术路径分析 |

## 辅助脚本（优先调用）

**AI 应优先调用下列脚本，而不是自由编写 SQL**。脚本使用 pysqlite3，遵循 watched_company / watched_university 规则，已测试。

工作目录需为 paper-map 工程根目录（或 PYTHONPATH 包含项目根）。

| 脚本 | 用途 | 用法示例 |
|------|------|----------|
| **list_watched.py** | 列出可查询的实体（供 AI 确认用户提及公司/高校是否在列表） | `python scripts/list_watched.py companies` |
| | | `python scripts/list_watched.py universities` |
| | | `python scripts/list_watched.py tags` |
| | | `python scripts/list_watched.py all --json` |
| **query_company.py** | 查询某关注公司某段时间的论文 | `python scripts/query_company.py 特斯拉 202401 202412` |
| | | `python scripts/query_company.py Google 202401 202412 --json` |
| **query_university.py** | 查询某关注高校的论文（可加标签） | `python scripts/query_university.py Stanford 202401 202412` |
| | | `python scripts/query_university.py 斯坦福 --tag 自动驾驶 --json` |
| **query_tag.py** | 按标签查询论文（支持模糊匹配） | `python scripts/query_tag.py 3DGS 202401 202412` |
| | | `python scripts/query_tag.py 自动驾驶.感知 --json` |
| **query_author.py** | 按作者查询论文 | `python scripts/query_author.py "Li" 202401 202412` |
| | | `python scripts/query_author.py 李华 --json` |
| **compare_companies.py** | 多关注公司论文数量对比 | `python scripts/compare_companies.py 202401 202412` |
| | | `python scripts/compare_companies.py --json` |

所有脚本支持 `--json` 输出，便于 AI 解析后生成总结。日期格式为 `yyyyMM`，如 202401。

## 注意事项

- `date` 格式为 `yyyyMM`，如 202401；可从 arxiv_id（如 2401.12345）推导
- **公司/高校**：必须从 `watched_company` / `watched_university` 获取 match_rule 构建查询，**勿自行定义** `LIKE '%X%'` 等匹配规则
- `company_names` / `university_names` 在视图中为逗号分隔；作者、标签等可自由用 `LIKE` 匹配
- 优先使用 `paper_based_view` 获取完整关联信息
- 查询后务必关闭连接
