#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多关注公司论文数量对比，按时间段统计。
仅统计关注公司，使用 watched_company 的 match_rule。

用法: python scripts/compare_companies.py [开始日期] [结束日期] [--json]
示例: python scripts/compare_companies.py 202401 202412
      python scripts/compare_companies.py --json
"""
import argparse
import json
import sys

from lib import get_db


def compare_companies(start_date: str, end_date: str) -> list[dict]:
    """
    统计各关注公司在指定时间段的论文数量。
    :param start_date: yyyyMM
    :param end_date: yyyyMM
    :return: [{"name": "公司显示名", "count": N, "papers": [...]}, ...]
    """
    db = get_db()
    matrix = db.get_car_company_paper_matrix()
    by_company = {}
    for r in matrix:
        name = r["company_name"]
        date_val = r.get("date") or ""
        if date_val and (date_val < start_date or date_val > end_date):
            continue
        if name not in by_company:
            by_company[name] = {"paper_ids": set(), "papers": []}
        if r["paper_id"] not in by_company[name]["paper_ids"]:
            by_company[name]["paper_ids"].add(r["paper_id"])
            by_company[name]["papers"].append({
                "paper_id": r["paper_id"],
                "arxiv_id": r.get("arxiv_id"),
                "alias": r.get("alias", ""),
                "date": r.get("date", ""),
            })
    result = [{"name": name, "count": len(d["papers"]), "papers": sorted(d["papers"], key=lambda p: (p.get("date") or "", p.get("paper_id", "")), reverse=True)} for name, d in by_company.items()]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="多关注公司论文数量对比")
    parser.add_argument("start_date", nargs="?", default="202001", help="开始日期 yyyyMM")
    parser.add_argument("end_date", nargs="?", default="203012", help="结束日期 yyyyMM")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    rows = compare_companies(args.start_date, args.end_date)

    if args.json:
        print(json.dumps({"start_date": args.start_date, "end_date": args.end_date, "companies": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"# 关注公司 {args.start_date}-{args.end_date} 论文数量对比\n")
        print("| 公司 | 论文数 |")
        print("|------|--------|")
        for r in rows:
            print(f"| {r['name']} | {r['count']} |")
        print()


if __name__ == "__main__":
    main()
