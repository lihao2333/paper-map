#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按标签查询论文，支持时间范围。
标签名支持模糊匹配（如 "BEV" 可匹配 "自动驾驶.BEV"）。

用法: python scripts/query_tag.py <标签名> [开始日期] [结束日期] [--json]
示例: python scripts/query_tag.py BEV 202401 202412
      python scripts/query_tag.py 自动驾驶.感知 --json
"""
import argparse
import json
import sys

from lib import get_db
from database import paper_list_sort_key


def query_tag_papers(tag_name: str, start_date: str, end_date: str) -> list[dict]:
    """
    按标签查询论文，支持模糊匹配标签名。
    :param tag_name: 标签名或部分匹配
    :param start_date: yyyyMM
    :param end_date: yyyyMM
    :return: 论文列表
    """
    db = get_db()
    tags = db.get_all_tags()
    tag_lower = tag_name.strip().lower()
    matched = [t for t in tags if tag_lower in (t.get("tag_name") or "").lower()]
    if not matched:
        raise ValueError(f"未找到标签「{tag_name}」。请运行 `python scripts/list_watched.py tags` 查看全部标签。")
    # 取第一个匹配
    tag_id = matched[0]["tag_id"]
    papers = db.get_papers_by_tag(tag_id)
    rows = []
    for p in papers:
        info = db.get_paper_info(paper_id=p["paper_id"])
        date_val = info.get("date") or ""
        if date_val and (date_val < start_date or date_val > end_date):
            continue
        rows.append({
            "paper_id": p["paper_id"],
            "arxiv_id": info.get("arxiv_id"),
            "paper_url": info.get("paper_url"),
            "alias": info.get("alias") or p.get("alias", ""),
            "full_name": info.get("full_name") or p.get("full_name", ""),
            "date": date_val,
            "abstract": info.get("abstract", ""),
            "summary": info.get("summary", "") or p.get("summary", ""),
        })
    rows.sort(key=paper_list_sort_key, reverse=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description="按标签查询论文")
    parser.add_argument("tag", help="标签名（支持模糊匹配）")
    parser.add_argument("start_date", nargs="?", default="202001", help="开始日期 yyyyMM")
    parser.add_argument("end_date", nargs="?", default="203012", help="结束日期 yyyyMM")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        rows = query_tag_papers(args.tag, args.start_date, args.end_date)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"tag": args.tag, "start_date": args.start_date, "end_date": args.end_date, "papers": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    else:
        print(f"# 标签「{args.tag}」{args.start_date}-{args.end_date} 论文\n")
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
