"""Validate a generated case CSV and import it into PostgreSQL."""

from __future__ import annotations

import csv
import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


from .paths import CONFIG_DIR, OUTPUT_DIR


DEFAULT_CONFIG = CONFIG_DIR / "kb_sync.local.json"
REQUIRED_COLUMNS = {"标题", "来源", "日期", "链接", "文件日期"}


def _parse_datetime(value: str, label: str, required: bool = True) -> datetime | None:
    value = value.strip()
    if not value and not required:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label}格式无效: {value or '空值'}") from exc


def read_cases(path: str | Path) -> list[dict[str, Any]]:
    """Parse and fully validate the UTF-8 BOM CSV before opening the database."""
    csv_path = Path(path)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
            missing = "、".join(sorted(REQUIRED_COLUMNS - set(reader.fieldnames or [])))
            raise ValueError(f"CSV缺少字段: {missing}")
        records: list[dict[str, Any]] = []
        for line_number, row in enumerate(reader, start=2):
            title = " ".join((row.get("标题") or "").split())
            if not title:
                raise ValueError(f"第 {line_number} 行标题不能为空")
            try:
                published = _parse_datetime(row.get("日期") or "", "日期")
                generated = _parse_datetime(row.get("文件日期") or "", "文件日期")
            except ValueError as exc:
                raise ValueError(f"第 {line_number} 行{exc}") from exc
            records.append(
                {
                    "title": title,
                    "source": (row.get("来源") or "").strip(),
                    "date": published,
                    "link": (row.get("链接") or "").strip(),
                    "file_date": generated,
                    "summary": row.get("摘要") or "",
                }
            )
    return records


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path or os.getenv("CASE_DB_CONFIG", DEFAULT_CONFIG))
    config: dict[str, Any] = {}
    try:
        if config_path.exists() or path is not None or os.getenv("CASE_DB_CONFIG"):
            payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
            config = dict(payload["database"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"数据库配置无法读取: {config_path}") from exc
    aliases = {"database": "NAME"}
    for key in ("host", "port", "database", "user", "password", "schema", "table"):
        value = os.getenv(f"CASE_DB_{aliases.get(key, key.upper())}")
        if key == "database" and value is None:
            value = os.getenv("CASE_DB_DATABASE")  # Older script configuration.
        if value is not None:
            config[key] = int(value) if key == "port" else value
    required = ("host", "port", "database", "user", "schema", "table")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise ValueError("数据库配置缺少: " + ", ".join(missing))
    return config


def import_csv(path: str | Path, config_path: str | Path | None = None) -> dict[str, int]:
    """Insert new cases by title/link, preserving existing rows on repeated runs."""
    records = read_cases(path)
    if not records:
        return {"inserted": 0, "skipped": 0}
    config = load_config(config_path)
    connection = psycopg.connect(
        host=config["host"], port=config["port"], dbname=config["database"],
        user=config["user"], password=config.get("password", ""), connect_timeout=5,
        row_factory=dict_row,
    )
    table = sql.Identifier(str(config["schema"]), str(config["table"]))
    inserted = skipped = 0
    seen: set[tuple[str, str]] = set()
    with connection:
        connection.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(table))
        next_id = connection.execute(
            sql.SQL("SELECT COALESCE(MAX(fid), 0) + 1 AS id FROM {}").format(table)
        ).fetchone()["id"]
        for record in records:
            key = (record["title"], record["link"])
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            exists = connection.execute(
                sql.SQL(
                    "SELECT 1 FROM {} WHERE fk_r8p0_title=%s AND fk_r8p0_link=%s LIMIT 1"
                ).format(table),
                key,
            ).fetchone()
            if exists:
                skipped += 1
                continue
            connection.execute(
                sql.SQL(
                    """INSERT INTO {} (fid, fk_r8p0_title, fk_r8p0_source,
                    fk_r8p0_link, fk_r8p0_date, fk_r8p0_file_date,
                    fk_r8p0_summary, fk_r8p0_sync_kb)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, '否')"""
                ).format(table),
                (next_id, record["title"], record["source"], record["link"],
                 record["date"], record["file_date"], record["summary"]),
            )
            next_id += 1
            inserted += 1
    return {"inserted": inserted, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将已有案例 CSV 导入数据库（重复案例自动跳过）")
    parser.add_argument("csv", type=Path, nargs="?", default=OUTPUT_DIR / "case.csv")
    parser.add_argument("--database-config", help="数据库 JSON 配置路径")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        outcome = import_csv(args.csv, args.database_config)
    except Exception as exc:
        logging.error("案例入库失败: %s", exc)
        return 1
    logging.info("案例入库完成：新增 %d 条，跳过 %d 条", outcome["inserted"], outcome["skipped"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
