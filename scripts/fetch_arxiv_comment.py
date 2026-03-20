#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按 arXiv ID 从 API 拉取元数据（标题、摘要、作者、PDF 链接、comment 等）。

一次运行只请求 arXiv 一次，多字段共用同一条 Result。

用法（在项目根目录执行）:
  python scripts/fetch_arxiv_comment.py 2108.02938
  python scripts/fetch_arxiv_comment.py 2108.02938 -f title -f comment
  python scripts/fetch_arxiv_comment.py 2512.14692v1 --all
  python scripts/fetch_arxiv_comment.py 2108.02938 --all --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arxiv_api import ArxivApi  # noqa: E402

FIELD_CHOICES = ("title", "abstract", "authors", "pdf_url", "comment")


def _comment_from_result(result: Any) -> str:
    c = getattr(result, "comment", None)
    if c is None:
        return ""
    return c.strip() if isinstance(c, str) else str(c).strip()


def _extract(result: Any, field: str) -> str | list[str]:
    if field == "title":
        return result.title
    if field == "abstract":
        return result.summary
    if field == "authors":
        return [a.name for a in result.authors]
    if field == "pdf_url":
        return result.pdf_url
    if field == "comment":
        return _comment_from_result(result)
    raise ValueError(field)


def main() -> int:
    p = argparse.ArgumentParser(
        description="查询单篇论文的 arXiv 元数据（默认仅 comment）"
    )
    p.add_argument("arxiv_id", help="arXiv ID，如 2108.02938 或 2512.14692v1")
    p.add_argument(
        "-f",
        "--field",
        action="append",
        choices=FIELD_CHOICES,
        dest="fields",
        metavar="NAME",
        help="要输出的字段，可重复；不写则等价于仅 comment",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="输出全部可用字段（title abstract authors pdf_url comment）",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 打印（authors 为字符串数组）",
    )
    args = p.parse_args()
    aid = args.arxiv_id.strip()
    if not aid:
        print("arxiv_id 不能为空", file=sys.stderr)
        return 2

    if args.all:
        fields = list(FIELD_CHOICES)
    elif args.fields:
        fields = args.fields
    else:
        fields = ["comment"]

    try:
        api = ArxivApi()
        result = api.get_result(aid)
    except Exception as e:
        print(f"获取失败: {e}", file=sys.stderr)
        return 1

    data: dict[str, Any] = {}
    for f in fields:
        v = _extract(result, f)
        data[f] = v

    if args.json:
        # JSON 需要可序列化结构
        out = dict(data)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if len(fields) == 1 and fields[0] == "comment":
        c = data["comment"]
        if c:
            print(c)
        else:
            print("(无 comment 或为空字符串)")
        return 0

    if len(fields) == 1:
        v = data[fields[0]]
        if fields[0] == "authors":
            print("\n".join(v))
        else:
            print(v)
        return 0

    for f in fields:
        v = data[f]
        if f == "authors":
            print(f"{f}:")
            for name in v:
                print(f"  {name}")
        else:
            print(f"{f}:")
            print(v if v else "(空)")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
