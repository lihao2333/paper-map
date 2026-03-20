---
name: paper-map
description: Query and summarize paper data from PaperMap. 支持按公司、高校、作者、标签、时间等维度检索论文，支持多公司对比、趋势分析、技术路线梳理、领域综述等。基本上所有与论文相关的需求（查某司/某校/某作者的论文、对比分析、主题统计、最新进展、技术路线等）都可用本 skill 完成。
---

# PaperMap 论文查询与总结

通过脚本查询 PaperMap 数据，并按用户要求生成总结。**AI 应优先调用脚本，不要直接操作数据库**。

## 脚本用法

工作目录需为 paper-map 工程根目录（或 PYTHONPATH 包含项目根）。

| 脚本 | 用途 | 用法示例 |
|------|------|----------|
| **list_watched.py** | 列出可查询的公司、高校、标签（确认用户提及的实体是否在列表中） | `python scripts/list_watched.py companies` |
| | | `python scripts/list_watched.py universities` |
| | | `python scripts/list_watched.py tags` |
| | | `python scripts/list_watched.py all --json` |
| **query_company.py** | 查询某关注公司某段时间的论文 | `python scripts/query_company.py 特斯拉 202401 202412` |
| | | `python scripts/query_company.py Google 202401 202412 --json` |
| **query_university.py** | 查询某关注高校的论文（可加标签筛选） | `python scripts/query_university.py Stanford 202401 202412` |
| | | `python scripts/query_university.py 斯坦福 --tag 自动驾驶 --json` |
| **query_tag.py** | 按标签查询论文（支持模糊匹配） | `python scripts/query_tag.py 3DGS 202401 202412` |
| | | `python scripts/query_tag.py 自动驾驶.感知 --json` |
| **query_author.py** | 按作者查询论文 | `python scripts/query_author.py "Li" 202401 202412` |
| | | `python scripts/query_author.py 李华 --json` |
| **compare_companies.py** | 多关注公司论文数量对比 | `python scripts/compare_companies.py 202401 202412` |
| | | `python scripts/compare_companies.py --json` |
| **completer.py** | 论文缓存/元数据补全（可原子步骤分跑） | `python completer.py --help`（`--only arxiv_metadata` 拉元数据并做 comment 结案；顶会 LLM 用 `--only ai_info_based_arxiv_meta_info`；正文 LLM 用 `--only ai_info_based_paper`） |

- 所有脚本支持 `--json` 输出，便于 AI 解析后生成总结
- 日期格式为 `yyyyMM`，如 202401

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
| | arxiv_comments | TEXT | arXiv API 返回的 comment 字段（录用/会议等） |
| | is_comment_used | INTEGER | 是否已对该 comment 做过会议解析并打标签（0/1） |
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

### 视图 `paper_based_view` / `paper_based_view_debug`

| 视图 | 用途 |
|------|------|
| **paper_based_view** | 仅 `paper` 表列 + 占位 `NULL` 聚合列，低成本全表扫描（统计、轻量查询） |
| **paper_based_view_debug** | 多表 JOIN + `GROUP_CONCAT` 全量聚合（公司/高校/作者/标签字符串），用于详情、批量 hover、`get_all_papers_with_details` 等 |

两视图**列序一致**；轻量视图中 `company_names` / `university_names` / `author_names` / `tag_names` 为 `NULL`。

**paper_based_view_debug** 常用列：

| 列名 | 说明 |
|------|------|
| paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary, arxiv_comments, is_comment_used | 同 paper 表 |
| company_names | 逗号分隔的公司名 |
| university_names | 逗号分隔的高校名 |
| author_names | 按 author_order 排序的作者名，逗号分隔 |
| tag_names | 逗号分隔的标签名 |

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
cursor.execute("SELECT * FROM paper_based_view_debug WHERE ...")  -- 需要聚合关联时
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
SELECT * FROM paper_based_view_debug
WHERE paper_id IN (
  SELECT paper_id FROM paper_university
  WHERE university_name IN (...) OR university_name LIKE ?  -- 由 watched_university 提供
)
AND paper_id IN (SELECT paper_id FROM paper_tag WHERE tag_id = (SELECT tag_id FROM tag WHERE tag_name = 'autonomous driving'));
```

### 4. 某作者近期工作

```sql
SELECT * FROM paper_based_view_debug
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
# [公司/高校名] [时间范围] 工作内容总结

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

## 注意事项

- 公司/高校维度：需在关注列表中，否则提示「该公司/高校不在关注列表中」，可先运行 `list_watched.py` 确认
- 时间范围支持 2024、2024Q1、202401-202412 等表述，脚本内部会解析
