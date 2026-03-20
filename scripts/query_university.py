#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询某关注高校的论文，可叠加标签或时间范围。
高校名必须对应数据库中 watched_university 的 name。

用法: python scripts/query_university.py <高校名> [开始日期] [结束日期] [--tag 标签名] [--json]
示例: python scripts/query_university.py 斯坦福 202401 202412
      python scripts/query_university.py Stanford --tag 自动驾驶 --json

需在工程根目录运行。
"""
import argparse
import json
import sys

from lib import get_db
from database import paper_list_sort_key


def _resolve_university_name(watched_universities: list[dict], name: str) -> str | None:
    """根据用户输入解析出 watched 中的 name。"""
    name_lower = name.strip().lower()
    for item in watched_universities:
        if name_lower in (item["name"] or "").lower():
            return item["name"]
        if name_lower in (item["match_rule"] or "").lower():
            return item["name"]
    return None


def query_university_papers(university_name: str, start_date: str, end_date: str, tag_name: str | None = None) -> list[dict]:
    """
    查询关注高校在指定时间段、可选标签的论文。
    :param university_name: 关注高校的显示名
    :param start_date: yyyyMM
    :param end_date: yyyyMM
    :param tag_name: 可选，标签名（支持层级或模糊匹配）
    :return: 论文列表
    """
    db = get_db()
    watched = db.get_all_watched_universities()
    resolved = _resolve_university_name(watched, university_name)
    if not resolved:
        raise ValueError(f"高校「{university_name}」不在关注列表中。请运行 `python scripts/list_watched.py universities` 查看。")

    matrix = db.get_university_paper_matrix()
    seen = set()
    rows = []
    for r in matrix:
        if r["university_name"] != resolved:
            continue
        date_val = r.get("date") or ""
        if date_val and (date_val < start_date or date_val > end_date):
            continue
        if r["paper_id"] in seen:
            continue
        seen.add(r["paper_id"])
        info = db.get_paper_info(paper_id=r["paper_id"])
        rows.append({
            "paper_id": r["paper_id"],
            "arxiv_id": info.get("arxiv_id"),
            "paper_url": info.get("paper_url"),
            "alias": info.get("alias") or r.get("alias", ""),
            "full_name": info.get("full_name") or r.get("full_name", ""),
            "date": r.get("date", ""),
            "abstract": info.get("abstract", ""),
            "summary": info.get("summary", "") or r.get("summary", ""),
        })

    if tag_name:
        tags = db.get_all_tags()
        tag_id = None
        for t in tags:
            if tag_name.strip().lower() in (t.get("tag_name") or "").lower():
                tag_id = t["tag_id"]
                break
        if tag_id is None:
            raise ValueError(f"未找到标签「{tag_name}」。请运行 `python scripts/list_watched.py tags` 查看。")
        tagged_ids = {p["paper_id"] for p in db.get_papers_by_tag(tag_id)}
        rows = [r for r in rows if r["paper_id"] in tagged_ids]

    rows.sort(key=paper_list_sort_key, reverse=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description="查询关注高校的论文")
    parser.add_argument("university", help="高校名")
    parser.add_argument("start_date", nargs="?", default="202001", help="开始日期 yyyyMM")
    parser.add_argument("end_date", nargs="?", default="203012", help="结束日期 yyyyMM")
    parser.add_argument("--tag", dest="tag_name", help="按标签筛选")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        rows = query_university_papers(args.university, args.start_date, args.end_date, args.tag_name)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"university": args.university, "tag": args.tag_name, "start_date": args.start_date, "end_date": args.end_date, "papers": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    else:
        print(f"# {args.university} {args.start_date}-{args.end_date} 工作内容总结\n")
        if args.tag_name:
            print(f"## 标签：{args.tag_name}\n")
        print(f"## 概览\n- 论文数量：{len(rows)} 篇\n")
        print("## 论文列表\n")
        for i, r in enumerate(rows, 1):
            title = r.get("alias") or r.get("full_name", "")
            print(f"{i}. **{title}** ({r.get('date', '')})")
            print(f"   - 链接：{r.get('paper_url', '')}")
            if r.get("abstract"):
                print(f"   - 摘要：{r['abstract'][:200]}...")
            print()


if __name__ == "__main__":
    main()
