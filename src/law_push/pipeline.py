#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crawl legal information and classify every item with a Dify agent.

Usage:
    python run_filter.py 30

The Dify app must be an agent/chat app because this script uses the
``/chat-messages`` API.  The agent is instructed to return exactly one of
``law``, ``case`` or ``other``.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime, timedelta
from typing import Iterable

from .classifier import DifyAgent, DifyError
from .database import import_csv
from .knowledge_base import synchronize
from .file_dates import format_file_date

from .settings import (
    CASE_OUTPUT_FILE,
    DEFAULT_DAYS,
    DIFY_API_KEY,
    DIFY_API_URL,
    LAW_OUTPUT_FILE,
    RESULT_OUTPUT_FILE,
)
from .crawler import LawCrawler
from .kingdee import KingdeeCaseClient, load_config


logger = logging.getLogger("law-push-filter")


def _date_of(crawler: LawCrawler, value: object) -> date | None:
    parsed = crawler._parse_date(str(value or ""))
    return parsed.date() if parsed else None


def unique_in_range(
    crawler: LawCrawler,
    items: Iterable[dict],
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Normalize, date-filter and de-duplicate crawler records."""
    output: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        item_date = _date_of(crawler, item.get("date"))
        if item_date is None or not (start_date <= item_date <= end_date):
            continue
        title = " ".join(str(item.get("title", "")).split())
        url = str(item.get("url", "")).strip()
        if not title:
            continue
        key = ("url", url) if url else ("title", title)
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(item)
        normalized["title"] = title
        normalized["url"] = url
        output.append(normalized)
    return sorted(output, key=lambda item: str(item.get("date", "")), reverse=True)


def run(days: int, agent: DifyAgent, keep_on_error: bool = False,
        file_date: str | date | None = None, case_client: KingdeeCaseClient | None = None,
        sync_kb: str | None = None, wecom_push: str | None = None,
        import_database: bool = True,
        database_config: str | None = None,
        sync_knowledge_base: bool = True) -> tuple[int, int, int]:
    if days < 1:
        raise ValueError("days must be at least 1")
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    crawler = LawCrawler(days=days)
    # Make the range inclusive by calendar date, independent of the 08:00 run time.
    crawler.cutoff_date = datetime.combine(start_date, datetime.min.time())

    logger.info("crawling %s through %s", start_date, end_date)
    crawler.crawl_all()
    items = unique_in_range(crawler, crawler.results, start_date, end_date)
    # Keep the complete, normalized crawl in result.txt. It is the input
    # snapshot for Dify and is intentionally not replaced by filtered output.
    crawler.save_items_file(RESULT_OUTPUT_FILE, items)
    source_cases = {(x.get("title"), x.get("url")) for x in crawler.case_results}

    law_items: list[dict] = []
    case_items: list[dict] = []
    other_count = 0
    for index, item in enumerate(items, start=1):
        try:
            category = agent.classify(item)
        except DifyError:
            if not keep_on_error:
                raise
            category = "case" if (item.get("title"), item.get("url")) in source_cases else "law"
            logger.exception("classification failed; keeping item as %s", category)

        if category == "law":
            law_items.append(item)
        elif category == "case":
            case_items.append(item)
        else:
            other_count += 1
        logger.info("classified %d/%d: %s", index, len(items), category)

    # Save only after every classification succeeds, so a failed run does not
    # overwrite the last successful result with unfiltered data.
    crawler.results = law_items + case_items
    crawler.case_results = case_items
    generated_date = format_file_date(file_date if file_date is not None else datetime.now())
    crawler.save_core_outputs(LAW_OUTPUT_FILE, CASE_OUTPUT_FILE, file_date=generated_date)
    logger.info("saved law=%d, case=%d, other=%d", len(law_items), len(case_items), other_count)
    if case_client is not None:
        count = case_client.send_cases(case_items, generated_date, sync_kb, wecom_push)
        logger.info("Kingdee case push succeeded: %d records", count)
    elif import_database:
        try:
            outcome = import_csv(CASE_OUTPUT_FILE, database_config)
        except Exception as exc:
            raise RuntimeError(f"case.csv database import failed: {exc}") from exc
        logger.info("database import succeeded: inserted=%d, skipped=%d",
                    outcome["inserted"], outcome["skipped"])
    if sync_knowledge_base and (import_database or case_client is not None):
        try:
            outcome = synchronize(database_config)
            if outcome["failed"]:
                raise RuntimeError(f"{outcome['failed']} cases failed to synchronize")
        except Exception as exc:
            raise RuntimeError(
                "database import completed, but knowledge base sync failed; "
                "retry with: python run_filter.py sync-kb "
                "(use the same --database-config if specified)"
            ) from exc
    return len(law_items), len(case_items), other_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl and filter legal information with a Dify agent")
    parser.add_argument("days", nargs="?", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--timeout", type=int, default=60, help="Dify request timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="retries per item")
    parser.add_argument("--keep-on-error", action="store_true", help="keep an item if Dify classification fails")
    parser.add_argument("--file-date", type=format_file_date, metavar="YYYY-MM-DD HH:MM:SS",
                        help="output file date (default: local date when saving)")
    parser.add_argument("--push-case", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-push-case", action="store_true",
                        help="save case.csv without database import or knowledge base sync")
    parser.add_argument("--no-sync-kb", action="store_true",
                        help="import case.csv into the database without knowledge base sync")
    parser.add_argument("--kingdee-config", help="Kingdee JSON config file")
    parser.add_argument("--kingdee-timeout", type=int, default=60)
    parser.add_argument("--sync-kb", choices=["是", "否"],
                        help="旧金蝶推送字段 r8p0_sync_kb（默认是）")
    parser.add_argument("--wecom-push", choices=["是", "否"],
                        help="旧金蝶推送字段 r8p0_wecom_push（默认否）")
    parser.add_argument("--database-config", help="database JSON config (default: config/kb_sync.local.json)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    api_url = os.getenv("DIFY_API_URL", DIFY_API_URL)
    api_key = os.getenv("DIFY_API_KEY", DIFY_API_KEY)
    if not api_key:
        logger.error("DIFY_API_KEY is empty")
        return 1
    try:
        case_client = (KingdeeCaseClient(load_config(args.kingdee_config), args.kingdee_timeout)
                       if args.push_case and not args.no_push_case else None)
        run(args.days, DifyAgent(api_url, api_key, args.timeout, args.retries),
            args.keep_on_error, args.file_date, case_client, args.sync_kb,
            args.wecom_push, import_database=not args.no_push_case, database_config=args.database_config,
            sync_knowledge_base=not args.no_sync_kb)
    except Exception:
        logger.exception("filtered crawl failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
