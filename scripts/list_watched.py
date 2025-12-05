#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
列出可查询的关注公司、关注高校、关注作者或标签。
供 AI 在查询前确认用户提及的实体是否在关注列表中。

用法: python scripts/list_watched.py [companies|universities|authors|tags] [--json]
示例: python scripts/list_watched.py companies
      python scripts/list_watched.py tags --json
"""
import argparse
import json
import sys

from lib import get_db


def main():
    parser = argparse.ArgumentParser(description="列出关注公司/高校/作者/标签")
    parser.add_argument("type", nargs="?", default="all", choices=["companies", "universities", "authors", "tags", "all"],
                       help="要列出的类型，默认 all")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    db = get_db()
    out = {}

    if args.type in ("companies", "all"):
        items = db.get_all_watched_companies()
        by_name = {}
        for item in items:
            n = item["name"]
            if n not in by_name:
                by_name[n] = []
            by_name[n].append(item["match_rule"])
        out["companies"] = [{"name": k, "match_rules": v} for k, v in by_name.items()]

    if args.type in ("universities", "all"):
        items = db.get_all_watched_universities()
        by_name = {}
        for item in items:
            n = item["name"]
            if n not in by_name:
                by_name[n] = []
            by_name[n].append(item["match_rule"])
        out["universities"] = [{"name": k, "match_rules": v} for k, v in by_name.items()]

    if args.type in ("authors", "all"):
        items = db.get_all_watched_authors()
        by_name = {}
        for item in items:
            n = item["name"]
            if n not in by_name:
                by_name[n] = []
            by_name[n].append(item["match_rule"])
        out["authors"] = [{"name": k, "match_rules": v} for k, v in by_name.items()]

    if args.type in ("tags", "all"):
        tags = db.get_all_tags()
        out["tags"] = [{"tag_id": t["tag_id"], "tag_name": t["tag_name"]} for t in tags]

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for key, val in out.items():
            print(f"## {key}\n")
            for v in val:
                if "match_rules" in v:
                    print(f"- {v['name']}: {', '.join(v['match_rules'])}")
                else:
                    print(f"- {v.get('tag_name', v.get('name', ''))} (id={v.get('tag_id', '')})")
            print()


if __name__ == "__main__":
    main()
