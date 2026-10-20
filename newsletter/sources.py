"""Fetch recently published papers from arXiv and journal RSS feeds."""

from __future__ import annotations

import calendar
import html
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser

log = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "research-newsletter/1.0 (+https://github.com/cshapiro17/cshapiro17)"


@dataclass
class Paper:
    id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    source: str
    published: datetime


def _clean(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    return None


def fetch_arxiv(categories: list[str], max_results: int, since: datetime) -> list[Paper]:
    papers: list[Paper] = []
    for i, category in enumerate(categories):
        if i:
            time.sleep(3)  # arXiv asks clients to wait 3s between API calls
        query = urllib.parse.urlencode({
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        })
        feed = feedparser.parse(f"{ARXIV_API}?{query}", agent=USER_AGENT)
        if feed.bozo and not feed.entries:
            log.warning("arXiv %s failed: %s", category, feed.bozo_exception)
            continue
        count = 0
        for entry in feed.entries:
            published = _entry_time(entry)
            if published is None or published < since:
                continue
            # "http://arxiv.org/abs/2410.12345v1" -> "2410.12345"
            arxiv_id = entry.id.rsplit("/abs/", 1)[-1].split("v")[0]
            papers.append(Paper(
                id=f"arxiv:{arxiv_id}",
                title=_clean(entry.title),
                authors=[a.name for a in entry.get("authors", [])],
                abstract=_clean(entry.get("summary", "")),
                url=f"https://arxiv.org/abs/{arxiv_id}",
                source=f"arXiv {category}",
                published=published,
            ))
            count += 1
        log.info("arXiv %s: %d recent papers", category, count)
    return papers


def fetch_feed(name: str, url: str, since: datetime) -> list[Paper]:
    feed = feedparser.parse(url, agent=USER_AGENT)
    if feed.bozo and not feed.entries:
        log.warning("Feed %r failed: %s", name, feed.bozo_exception)
        return []
    papers = []
    for entry in feed.entries:
        link = entry.get("link")
        if not link:
            continue
        # Journal tables of contents often omit dates; treat undated entries as
        # new and let the seen-paper history drop repeats.
        published = _entry_time(entry) or datetime.now(timezone.utc)
        if published < since:
            continue
        authors = [a.get("name", "") for a in entry.get("authors", [])]
        if not authors and entry.get("author"):
            authors = [entry.author]
        papers.append(Paper(
            id=f"url:{link}",
            title=_clean(entry.get("title", "")),
            authors=[a for a in authors if a],
            abstract=_clean(entry.get("summary", "")),
            url=link,
            source=name,
            published=published,
        ))
    log.info("%s: %d recent papers", name, len(papers))
    return papers


def fetch_all(config: dict) -> list[Paper]:
    since = datetime.now(timezone.utc) - timedelta(days=config["newsletter"]["lookback_days"])
    arxiv = config.get("arxiv", {})
    papers = fetch_arxiv(arxiv.get("categories", []), arxiv.get("max_results_per_category", 200), since)
    for feed in config.get("feeds", []):
        try:
            papers.extend(fetch_feed(feed["name"], feed["url"], since))
        except Exception:  # one bad feed shouldn't sink the newsletter
            log.exception("Feed %r raised", feed["name"])

    # The same arXiv paper is often cross-listed in several categories.
    unique: dict[str, Paper] = {}
    for paper in papers:
        unique.setdefault(paper.id, paper)
    return sorted(unique.values(), key=lambda p: p.published, reverse=True)
