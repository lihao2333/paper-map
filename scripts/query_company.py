#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询某关注公司某段时间的论文。
公司名必须对应数据库中 watched_company 的 name，使用其 match_rule 匹配。

用法: python scripts/query_company.py <公司名> [开始日期] [结束日期] [--json]
示例: python scripts/query_company.py 特斯拉 202401 202412
      python scripts/query_company.py Tesla 202401 202412 --json

需在工程根目录运行，或确保 PYTHONPATH 包含项目根。
"""
import argparse
import json
import sys

from lib import get_db


def _resolve_company_name(watched_companies: list[dict], name: str) -> str | None:
    """根据用户输入解析出 watched 中的 name（显示名）。支持 name 或 match_rule 的模糊匹配。"""
    name_lower = name.strip().lower()
    for item in watched_companies:
        if name_lower in (item["name"] or "").lower():
            return item["name"]
        if name_lower in (item["match_rule"] or "").lower():
            return item["name"]
    return None


def query_company_papers(company_name: str, start_date: str, end_date: str) -> list[dict]:
    """
    查询关注公司在指定时间段的论文。
    :param company_name: 关注公司的显示名（watched_company.name）
    :param start_date: yyyyMM
    :param end_date: yyyyMM
    :return: 论文列表，每项含 paper_id, arxiv_id, paper_url, alias, full_name, date, abstract, summary
    """
    db = get_db()
    watched = db.get_all_watched_companies()
    resolved = _resolve_company_name(watched, company_name)
    if not resolved:
        raise ValueError(f"公司「{company_name}」不在关注列表中。请运行 `python scripts/list_watched.py companies` 查看可查询公司。")

    matrix = db.get_car_company_paper_matrix()
    seen = set()
    rows = []
    for r in matrix:
        if r["company_name"] != resolved:
            continue
        date_val = r.get("date") or ""
        if date_val and (date_val < start_date or date_val > end_date):
            continue
        if r["paper_id"] in seen:
            continue
        seen.add(r["paper_id"])
        # 补充完整信息
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
    rows.sort(key=lambda x: (x.get("date") or "", x.get("paper_id", "")), reverse=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description="查询关注公司某段时间的论文")
    parser.add_argument("company", help="公司名（对应关注列表中的 name 或 match_rule）")
    parser.add_argument("start_date", nargs="?", default="202001", help="开始日期 yyyyMM，默认 202001")
    parser.add_argument("end_date", nargs="?", default="203012", help="结束日期 yyyyMM，默认 203012")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式供 AI 解析")
    args = parser.parse_args()

    try:
        rows = query_company_papers(args.company, args.start_date, args.end_date)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"company": args.company, "start_date": args.start_date, "end_date": args.end_date, "papers": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    else:
        print(f"# {args.company} {args.start_date}-{args.end_date} 工作内容总结\n")
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
