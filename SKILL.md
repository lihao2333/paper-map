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

- 所有脚本支持 `--json` 输出，便于 AI 解析后生成总结
- 日期格式为 `yyyyMM`，如 202401

## 输出总结

当用户要求总结某公司/高校某段时间的工作内容时，可参考结构：

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
