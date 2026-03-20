#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将数据库中 venue.* 标签去掉末尾年份（venue.NeurIPS2024 -> venue.NeurIPS）。
用法:
  python scripts/migrate_venue_tags.py              # 执行迁移
  python scripts/migrate_venue_tags.py --dry-run    # 仅预览
  python scripts/migrate_venue_tags.py --db /path/to/database.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Database


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 venue 标签：去掉末尾年份")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="数据库路径（默认项目 data/database.db）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将执行的变更，不写库",
    )
    args = parser.parse_args()
    db_path = args.db or (ROOT / "data" / "database.db")
    if not db_path.is_file():
        print(f"错误: 数据库不存在: {db_path}", file=sys.stderr)
        return 1

    db = Database(str(db_path))
    r = db.migrate_venue_tags_strip_year(dry_run=args.dry_run)
    print(
        f"扫描 venue.* 标签: {r['examined']} 个；"
        f"将变更: {r['changed']} 个；不变: {r['unchanged']} 个"
        + (" [dry-run]" if r["dry_run"] else "")
    )
    for old, new, tid in r["moves"][:200]:
        print(f"  [{tid}] {old} -> {new}")
    if len(r["moves"]) > 200:
        print(f"  ... 另有 {len(r['moves']) - 200} 条未列出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
