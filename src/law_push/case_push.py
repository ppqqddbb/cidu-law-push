"""Send an existing case.txt or case.csv without crawling or classifying again."""

import argparse
import csv
import logging
from .file_dates import format_file_date
from pathlib import Path

from .settings import CASE_OUTPUT_FILE
from .kingdee import KingdeeCaseClient, load_config


FIELDS = {"标题": "title", "来源": "source", "日期": "date", "链接": "url",
          "文件日期": "file_date", "摘要": "summary"}


def read_cases(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"标题", "来源", "日期", "链接"}.issubset(reader.fieldnames or []):
                raise ValueError("CSV must contain 标题、来源、日期、链接")
            return [{key: row.get(label, "") for label, key in FIELDS.items()}
                    for row in reader]
    if path.suffix.lower() != ".txt":
        raise ValueError("Input file must be .txt or .csv")
    items, current = [], {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        label, separator, value = line.partition("：")
        if not separator:
            label, separator, value = line.partition(":")
        if label.strip() not in FIELDS:
            continue
        key = FIELDS[label.strip()]
        if key == "title" and current:
            items.append(current)
            current = {}
        current[key] = value.strip()
    if current:
        items.append(current)
    return items


def main(argv=None):
    parser = argparse.ArgumentParser(description="Push case.txt/case.csv to Kingdee")
    parser.add_argument("input", nargs="?", default=CASE_OUTPUT_FILE)
    parser.add_argument("--config", help="Kingdee JSON config file")
    parser.add_argument("--file-date", type=format_file_date, metavar="YYYY-MM-DD HH:MM:SS",
                        help="override file date; required for older four-field files")
    parser.add_argument("--sync-kb", choices=["是", "否"],
                        help="value for r8p0_sync_kb (default: 是)")
    parser.add_argument("--wecom-push", choices=["是", "否"],
                        help="value for r8p0_wecom_push (default: 否)")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        client = KingdeeCaseClient(load_config(args.config), timeout=args.timeout)
        count = client.send_cases(read_cases(args.input),
                                  args.file_date,
                                  args.sync_kb,
                                  args.wecom_push)
        logging.info("Kingdee case push succeeded: %d records", count)
    except (OSError, ValueError, RuntimeError) as exc:
        logging.error("Kingdee case push failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
