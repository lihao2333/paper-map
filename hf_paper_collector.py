#!/usr/bin/env python3
"""
Collect HuggingFace papers (daily, trending, weekly, monthly),
insert into database with appropriate tags, clean up stale tags,
then run the Completer enrichment pipeline.

Usage:
    python hf_paper_collector.py
    python hf_paper_collector.py --skip-complete   # insert+tag only, no PDF/AI enrichment
    python hf_paper_collector.py --dry-run         # print what would happen, no DB writes
"""

import argparse
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from completer import Completer
from config import get_db_path
from database import Database
from fetch_hf_papers import (
    _current_iso_week,
    _current_month,
    fetch_hf_daily_papers,
    fetch_hf_monthly_papers,
    fetch_hf_trending_papers,
    fetch_hf_weekly_papers,
)

HF_DAILY_TAG = "hf_daily_paper"
HF_TRENDING_TAG = "hf_trending_paper"
HF_WEEKLY_TAG = "hf_weekly_paper"
HF_MONTHLY_TAG = "hf_monthly_paper"

ALL_HF_TAGS = [HF_DAILY_TAG, HF_TRENDING_TAG, HF_WEEKLY_TAG, HF_MONTHLY_TAG]


def _fetch_all_categories() -> dict[str, list[dict]]:
    """
    Fetch papers from all four HF categories for the current date.
    Returns dict mapping tag_name -> list of paper dicts.
    """
    year_w, week = _current_iso_week()
    year_m, month = _current_month()

    print("Fetching HF daily papers...")
    daily = fetch_hf_daily_papers()
    print(f"  {len(daily)} papers")
    time.sleep(1)

    print("Fetching HF trending papers...")
    trending = fetch_hf_trending_papers()
    print(f"  {len(trending)} papers")
    time.sleep(1)

    print(f"Fetching HF weekly papers ({year_w}-W{week})...")
    weekly = fetch_hf_weekly_papers(year_w, week)
    print(f"  {len(weekly)} papers")
    time.sleep(1)

    print(f"Fetching HF monthly papers ({year_m}-{month:02d})...")
    monthly = fetch_hf_monthly_papers(year_m, month)
    print(f"  {len(monthly)} papers")

    return {
        HF_DAILY_TAG: daily,
        HF_TRENDING_TAG: trending,
        HF_WEEKLY_TAG: weekly,
        HF_MONTHLY_TAG: monthly,
    }


def _merge_papers(categories: dict[str, list[dict]]) -> list[dict]:
    """
    Merge papers from all categories, deduplicating by arxiv_id.
    Each merged paper has a 'tags' set with all applicable HF tag names.
    Papers without arxiv_id are keyed by title to avoid duplicates.

    Returns list of:
    {
        "title": str,
        "arxiv_id": str | None,
        "arxiv_url": str | None,
        "github_url": str | None,
        "tags": set[str],
    }
    """
    merged: dict[str, dict] = {}  # key -> paper dict

    for tag_name, papers in categories.items():
        for paper in papers:
            arxiv_id = paper.get("arxiv_id")
            key = arxiv_id if arxiv_id else f"title:{paper['title']}"

            if key not in merged:
                merged[key] = {
                    "title": paper["title"],
                    "arxiv_id": arxiv_id,
                    "arxiv_url": paper.get("arxiv_url"),
                    "github_url": paper.get("github_url"),
                    "tags": set(),
                }
            else:
                # Keep github_url if we now have one and didn't before
                if not merged[key]["github_url"] and paper.get("github_url"):
                    merged[key]["github_url"] = paper["github_url"]

            merged[key]["tags"].add(tag_name)

    return list(merged.values())


_HF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_github_url_from_detail(arxiv_id: str, retries: int = 3) -> str | None:
    """Fetch the HF paper detail page and extract the GitHub repo URL (if any).
    Retries up to `retries` times on 429/5xx with exponential backoff.
    """
    url = f"https://huggingface.co/papers/{arxiv_id}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=_HF_HEADERS, timeout=15)
            if resp.status_code == 429:
                wait = 2**attempt * 2  # 2, 4, 8 seconds
                time.sleep(wait)
                continue
            resp.raise_for_status()
        except Exception:
            if attempt < retries - 1:
                time.sleep(2**attempt)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if (
                re.match(r"https?://(www\.)?github\.com/", href)
                and "github.com/huggingface" not in href
            ):
                return href
        return None
    return None


def _enrich_github_urls(papers: list[dict], max_workers: int = 3) -> None:
    """
    For papers without a github_url, fetch the HF detail page and fill it in.
    Modifies papers in-place. Only processes papers with an arxiv_id.
    """
    to_enrich = [p for p in papers if p.get("arxiv_id") and not p.get("github_url")]
    if not to_enrich:
        return
    print(
        f"\nFetching GitHub URLs for {len(to_enrich)} papers without GitHub info, using up to {max_workers} workers..."
    )
    found = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_github_url_from_detail, p["arxiv_id"]): p
            for p in to_enrich
        }
        for future in as_completed(futures):
            paper = futures[future]
            github_url = future.result()
            if github_url:
                paper["github_url"] = github_url
                found += 1
    print(f"  Found GitHub URLs for {found}/{len(to_enrich)} papers")


def _remove_stale_tags(db: Database, categories: dict[str, list[dict]], dry_run: bool):
    """
    For each HF tag, find papers in DB that currently have that tag
    but are NOT in the current fetch results. Remove the tag from those papers.

    NOTE: HF tags are only ever applied to papers where paper_id == arxiv_id
    (enforced by the insert logic in collect()). The stale check compares
    paper_id against current arxiv_ids directly. If a paper_id is found that
    has no matching arxiv_id in the DB (edge case: manually tagged), we look
    up its arxiv_id via get_paper_info() before comparing.
    """
    for tag_name, papers in categories.items():
        # arxiv_ids currently in this category
        current_ids = {p["arxiv_id"] for p in papers if p.get("arxiv_id")}

        # paper_ids in DB that have this tag
        tagged_paper_ids = db.get_papers_by_tag_name(tag_name)

        for paper_id in tagged_paper_ids:
            # For HF-inserted papers, paper_id == arxiv_id.
            # Guard against papers tagged externally where paper_id != arxiv_id:
            # look up the arxiv_id and use that for the comparison.
            compare_id = paper_id
            if paper_id not in current_ids:
                info = db.get_paper_info(paper_id=paper_id)
                if info and info.get("arxiv_id") and info["arxiv_id"] != paper_id:
                    compare_id = info["arxiv_id"]

            if compare_id not in current_ids:
                # Get tag_id
                paper_tags = db.get_paper_tags(paper_id)
                for t in paper_tags:
                    if t["tag_name"] == tag_name:
                        if dry_run:
                            print(
                                f"  [dry-run] Would remove tag '{tag_name}' from {paper_id}"
                            )
                        else:
                            db.remove_tag_from_paper(paper_id, t["tag_id"])
                            print(f"  Removed stale tag '{tag_name}' from {paper_id}")


def collect(skip_complete: bool = False, dry_run: bool = False):
    db_path = get_db_path()
    db = Database(db_path)
    db.construct()

    # 1. Fetch all categories
    categories = _fetch_all_categories()

    # 2. Merge + dedup
    papers = _merge_papers(categories)
    print(f"\nTotal unique papers: {len(papers)}")

    # 3. Enrich missing GitHub URLs from HF detail pages
    if not dry_run:
        _enrich_github_urls(papers)

    # 4. Remove stale tags
    print("\nCleaning up stale HF tags...")
    _remove_stale_tags(db, categories, dry_run)

    # 5. Insert papers + apply tags
    new_count = 0
    for paper in papers:
        arxiv_id = paper["arxiv_id"]
        if not arxiv_id:
            print(f"  Skipping paper without arxiv_id: {paper['title'][:60]}")
            continue

        paper_id = arxiv_id
        paper_url = paper["arxiv_url"] or f"https://arxiv.org/abs/{arxiv_id}"

        # Extract date from arxiv_id (format: YYMM.NNNNN -> yyyyMM)
        date = Database._extract_date_from_arxiv_id(arxiv_id)

        if dry_run:
            print(f"  [dry-run] Would insert {arxiv_id} with tags {paper['tags']}")
            continue

        # Insert (INSERT OR IGNORE — existing papers are untouched)
        existing = db.get_paper_info(paper_id=paper_id)
        if existing is None:
            db.insert_paper(
                [
                    {
                        "paper_id": paper_id,
                        "arxiv_id": arxiv_id,
                        "paper_url": paper_url,
                        "date": date,
                        "alias": None,
                        "full_name": paper["title"],
                        "abstract": None,
                        "github_url": paper.get("github_url"),
                    }
                ]
            )
            new_count += 1
            print(f"  Inserted: {arxiv_id}  tags={paper['tags']}")
        else:
            # Update github_url if we have one and DB doesn't
            if paper.get("github_url") and not existing.get("github_url"):
                db.update_github_url(paper_id, paper["github_url"])

        # Apply HF tags (add_tag_to_paper is idempotent)
        for tag_name in paper["tags"]:
            db.add_tag_to_paper(paper_id, tag_name)

    if dry_run:
        print("\n[dry-run] No changes written to database.")
        return

    print(f"\nInserted {new_count} new papers.")

    # 6. Run Completer enrichment pipeline
    if not skip_complete:
        print("\nRunning Completer enrichment pipeline...")
        completer = Completer("./cache", db)
        completer.complete_new(group_size=30, max_workers=10)
    else:
        print("\n--skip-complete set, skipping enrichment pipeline.")


def main():
    parser = argparse.ArgumentParser(
        description="Collect HuggingFace papers and insert into database"
    )
    parser.add_argument(
        "--skip-complete",
        action="store_true",
        help="Skip the Completer enrichment pipeline (insert + tag only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without writing to database",
    )
    args = parser.parse_args()
    collect(skip_complete=args.skip_complete, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
