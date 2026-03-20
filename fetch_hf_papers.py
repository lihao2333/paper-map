#!/usr/bin/env python3
"""
Fetch papers from HuggingFace paper pages.

Public API:
  fetch_hf_daily_papers()             -> list[dict]
  fetch_hf_trending_papers()          -> list[dict]
  fetch_hf_weekly_papers(year, week)  -> list[dict]
  fetch_hf_monthly_papers(year, month)-> list[dict]

Each returns list of:
  {
    "title": str,
    "arxiv_id": str | None,
    "arxiv_url": str | None,
    "github_url": str | None,
  }
"""

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HF_BASE_URL = "https://huggingface.co/papers"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_papers_from_url(url: str) -> list[dict]:
    """Scrape a HuggingFace papers page and return paper dicts."""
    response = requests.get(url, headers=_HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    papers = []

    for article in soup.find_all("article"):
        title_tag = article.find("h3")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue

        arxiv_id = None
        arxiv_url = None
        github_url = None

        for a in article.find_all("a", href=True):
            href = a["href"]

            # HF internal paper link: /papers/2401.12345
            if arxiv_id is None:
                m = re.search(r"/papers/(\d{4}\.\d{4,5})", href)
                if m:
                    arxiv_id = m.group(1)
                    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"

            # GitHub link
            if github_url is None:
                if re.match(r"https?://(www\.)?github\.com/", href):
                    github_url = href

        papers.append(
            {
                "title": title,
                "arxiv_id": arxiv_id,
                "arxiv_url": arxiv_url,
                "github_url": github_url,
            }
        )

    return papers


def fetch_hf_daily_papers() -> list[dict]:
    """Fetch today's papers from https://huggingface.co/papers"""
    return _fetch_papers_from_url(HF_BASE_URL)


def fetch_hf_trending_papers() -> list[dict]:
    """Fetch trending papers from https://huggingface.co/papers/trending"""
    return _fetch_papers_from_url(f"{HF_BASE_URL}/trending")


def fetch_hf_weekly_papers(year: int, week: int) -> list[dict]:
    """
    Fetch papers for a given ISO week.
    URL format: https://huggingface.co/papers/week/YYYY-W<n>
    Example: fetch_hf_weekly_papers(2026, 12)
    """
    url = f"{HF_BASE_URL}/week/{year}-W{week}"
    return _fetch_papers_from_url(url)


def fetch_hf_monthly_papers(year: int, month: int) -> list[dict]:
    """
    Fetch papers for a given month.
    URL format: https://huggingface.co/papers/month/YYYY-MM
    Example: fetch_hf_monthly_papers(2026, 3)
    """
    url = f"{HF_BASE_URL}/month/{year}-{month:02d}"
    return _fetch_papers_from_url(url)


def _current_iso_week() -> tuple[int, int]:
    """Return (year, week) for today's ISO week."""
    today = datetime.now()
    iso = today.isocalendar()
    return iso[0], iso[1]


def _current_month() -> tuple[int, int]:
    """Return (year, month) for today."""
    today = datetime.now()
    return today.year, today.month


if __name__ == "__main__":
    print("=== Daily ===")
    daily = fetch_hf_daily_papers()
    print(f"Found {len(daily)} papers")
    for p in daily[:3]:
        print(f"  {p['title'][:60]}  arxiv={p['arxiv_id']}  github={p['github_url']}")

    print("\n=== Trending ===")
    trending = fetch_hf_trending_papers()
    print(f"Found {len(trending)} papers")
    for p in trending[:3]:
        print(f"  {p['title'][:60]}  arxiv={p['arxiv_id']}  github={p['github_url']}")

    year, week = _current_iso_week()
    print(f"\n=== Weekly ({year}-W{week}) ===")
    weekly = fetch_hf_weekly_papers(year, week)
    print(f"Found {len(weekly)} papers")

    year, month = _current_month()
    print(f"\n=== Monthly ({year}-{month:02d}) ===")
    monthly = fetch_hf_monthly_papers(year, month)
    print(f"Found {len(monthly)} papers")
