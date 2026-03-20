#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按作者查询论文，支持时间范围。
作者名支持模糊匹配 author_names 字段。

用法: python scripts/query_author.py <作者名> [开始日期] [结束日期] [--json]
示例: python scripts/query_author.py "John Smith" 202401 202412
      python scripts/query_author.py 李华 --json
"""
import argparse
import json
import sys

from lib import get_db, sqlite3


def _tags_from_row(r: sqlite3.Row) -> list:
    """与 database 中 tag_names（GROUP_CONCAT）解析一致"""
    raw = r["tag_names"]
    if raw is None:
        return []
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def query_author_papers(author_name: str, start_date: str, end_date: str) -> list[dict]:
    """
    按作者查询论文。
    :param author_name: 作者名（模糊匹配）
    :param start_date: yyyyMM
    :param end_date: yyyyMM
    :return: 论文列表
    """
    db = get_db()
    db_path = db._path  # noqa: SLF001
    pattern = f"%{author_name.strip()}%"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT paper_id, arxiv_id, paper_url, date, alias, full_name, abstract, summary,
                   company_names, university_names, author_names, arxiv_comments, is_comment_used, tag_names
            FROM paper_based_view
            WHERE author_names LIKE ? AND date BETWEEN ? AND ?
            ORDER BY
                (CASE WHEN arxiv_id IS NOT NULL AND TRIM(arxiv_id) != '' THEN 1 ELSE 0 END) DESC,
                arxiv_id DESC,
                date DESC,
                paper_id
        """, (pattern, start_date, end_date))
        rows = [dict(r) for r in cur.fetchall()]

    result = []
    for r in rows:
        result.append({
            "paper_id": r["paper_id"],
            "arxiv_id": r["arxiv_id"],
            "paper_url": r["paper_url"],
            "alias": r["alias"] or "",
            "full_name": r["full_name"] or "",
            "date": r["date"] or "",
            "abstract": r["abstract"] or "",
            "summary": r["summary"] or "",
            "tags": _tags_from_row(r),
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="按作者查询论文")
    parser.add_argument("author", help="作者名（模糊匹配）")
    parser.add_argument("start_date", nargs="?", default="202001", help="开始日期 yyyyMM")
    parser.add_argument("end_date", nargs="?", default="203012", help="结束日期 yyyyMM")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        rows = query_author_papers(args.author, args.start_date, args.end_date)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"author": args.author, "start_date": args.start_date, "end_date": args.end_date, "papers": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    else:
        print(f"# 作者「{args.author}」{args.start_date}-{args.end_date} 论文\n")
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
