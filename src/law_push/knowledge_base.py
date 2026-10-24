"""Synchronize PostgreSQL cases marked 是否同步到知识库=否 to Dify."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import requests

from .database import load_config as load_database_config

from .paths import CONFIG_DIR

CFG = CONFIG_DIR / "kb_sync.local.json"
FIELDS = "fid, fk_r8p0_title, fk_r8p0_source, fk_r8p0_link, fk_r8p0_date, fk_r8p0_file_date, fk_r8p0_summary"
UNSYNCED = "否"
SYNCED = "是"
logger = logging.getLogger(__name__)


def load(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path or os.getenv("CASE_DB_CONFIG", CFG))
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    config["database"] = load_database_config(path)
    dify = config.setdefault("dify", {})
    for field, variable in {
        "api_key": "DIFY_KB_API_KEY",
        "base_url": "DIFY_KB_BASE_URL",
        "dataset_id": "DIFY_KB_DATASET_ID",
        "dataset_name": "DIFY_KB_DATASET_NAME",
    }.items():
        if variable in os.environ:
            dify[field] = os.environ[variable]
    return config


def value(row, key, index):
    """Read either psycopg dict rows or ordinary tuple rows."""
    return row.get(key) if hasattr(row, "get") else row[index]


def content(row):
    return "\n".join(f"{label}：{value(row, field, index) or ''}" for label, field, index in [
        ("标题", "fk_r8p0_title", 1), ("来源", "fk_r8p0_source", 2),
        ("链接", "fk_r8p0_link", 3), ("日期", "fk_r8p0_date", 4),
        ("文件日期", "fk_r8p0_file_date", 5), ("摘要", "fk_r8p0_summary", 6)])


def resolve_dataset(session: requests.Session, dify: dict[str, Any]) -> str:
    if dify.get("dataset_id"):
        return str(dify["dataset_id"])
    matches = []
    page = 1
    while True:
        response = session.get(dify["base_url"].rstrip("/") + "/datasets",
                               params={"page": page, "limit": 100}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        matches.extend(item["id"] for item in payload.get("data", [])
                       if item.get("name") == dify.get("dataset_name"))
        if not payload.get("has_more"):
            break
        page += 1
    if len(matches) != 1:
        raise ValueError("未找到唯一知识库，请在 kb_sync.local.json 填写 dify.dataset_id")
    return str(matches[0])


def disable_old_documents(session: requests.Session, dify: dict[str, Any], dataset_id: str) -> int:
    """Disable all documents in the specified dataset before syncing new ones.

    Returns the count of disabled documents.
    """
    disabled_count = 0
    page = 1
    base_url = dify["base_url"].rstrip("/")

    while True:
        # List documents in the dataset
        list_url = f"{base_url}/datasets/{dataset_id}/documents"
        response = session.get(list_url, params={"page": page, "limit": 100}, timeout=30)
        response.raise_for_status()
        payload = response.json()

        documents = payload.get("data", [])
        for doc in documents:
            doc_id = doc.get("id")
            if doc_id and doc.get("enabled", True):
                # Disable the document
                update_url = f"{base_url}/datasets/{dataset_id}/documents/{doc_id}/status"
                try:
                    update_response = session.post(
                        update_url,
                        json={"enabled": False},
                        timeout=30
                    )
                    update_response.raise_for_status()
                    disabled_count += 1
                    logger.info("已禁用知识库文档: %s", doc_id)
                except requests.RequestException as exc:
                    logger.warning("禁用文档 %s 失败: %s", doc_id, exc)

        if not payload.get("has_more"):
            break
        page += 1

    return disabled_count


def synchronize(config_path: str | Path | None = None, *, dry_run: bool = False,
                limit: int | None = None, disable_old: bool = True) -> dict[str, int]:
    """Submit unsynchronized cases in batches and mark each accepted document.

    Dify indexes accepted documents asynchronously. Accepted submissions are
    recorded as 是; rejected submissions stay 否 for the next invocation.
    Rows without a status (NULL or empty) are treated as not yet synchronized.

    If disable_old is True, disables all existing documents in the target dataset
    before syncing new ones.
    """
    if limit is not None and limit < 1:
        raise ValueError("limit 必须大于 0")
    config = load(config_path)
    database, dify = config["database"], config["dify"]
    if not dry_run and (not dify.get("api_key") or not dify.get("base_url")):
        raise ValueError("请配置 dify.base_url 和 dify.api_key（或 DIFY_KB_API_KEY）")
    table = sql.Identifier(database["schema"], database["table"])
    outcome = {"synced": 0, "failed": 0, "skipped": 0, "pending": 0}
    with psycopg.connect(host=database["host"], port=database["port"],
                         dbname=database["database"], user=database["user"],
                         password=database.get("password", ""), connect_timeout=5,
                         row_factory=dict_row, autocommit=True) as db:
        # Bound this run to existing records; later inserts are picked up next time.
        pending = db.execute(sql.SQL(
            "SELECT COUNT(*) AS count, MAX(fid) AS max_id FROM {} "
            "WHERE COALESCE(fk_r8p0_sync_kb, '') <> %s"
        ).format(table), (UNSYNCED,)).fetchone()
        outcome["pending"] = pending["count"]
        if dry_run or not outcome["pending"]:
            logger.info("待同步 %d 条", outcome["pending"])
            return outcome
        with requests.Session() as session:
            session.headers.update({"Authorization": "Bearer " + dify["api_key"],
                                    "Content-Type": "application/json"})
            dataset = resolve_dataset(session, dify)

            # Disable old documents in this specific dataset only
            if disable_old:
                try:
                    disabled = disable_old_documents(session, dify, dataset)
                    logger.info("已禁用 %d 个旧文档（知识库 ID: %s）", disabled, dataset)
                except Exception as exc:
                    logger.warning("禁用旧文档时出错: %s", exc)

            endpoint = f"{dify['base_url'].rstrip('/')}/datasets/{dataset}/document/create-by-text"
            last_id = None
            attempted = 0
            while limit is None or attempted < limit:
                batch_size = min(100, limit - attempted) if limit else 100
                condition = sql.SQL("") if last_id is None else sql.SQL(" AND fid > %s")
                params = (UNSYNCED,) + (pending["max_id"],) + (() if last_id is None else (last_id,)) + (batch_size,)
                rows = db.execute(sql.SQL(
                    "SELECT fid FROM {} WHERE COALESCE(fk_r8p0_sync_kb, '') <> %s "
                    "AND fid <= %s{} ORDER BY fid LIMIT %s"
                ).format(table, condition), params).fetchall()
                if not rows:
                    break
                for candidate in rows:
                    fid = candidate["fid"]
                    last_id = fid
                    attempted += 1
                    try:
                        # Concurrent runs cannot submit the same row simultaneously.
                        with db.transaction():
                            row = db.execute(sql.SQL(
                                "SELECT " + FIELDS + " FROM {} WHERE fid=%s "
                                "AND COALESCE(fk_r8p0_sync_kb, '') <> %s "
                                "FOR UPDATE SKIP LOCKED"
                            ).format(table), (fid, SYNCED)).fetchone()
                            if row is None:
                                outcome["skipped"] += 1
                                continue
                            response = session.post(endpoint, json={
                                "name": f"case-{fid}", "text": content(row),
                                "indexing_technique": "high_quality",
                                "process_rule": {"mode": "automatic"},
                            }, timeout=60)
                            response.raise_for_status()
                            payload = response.json()
                            document = payload.get("document")
                            if not isinstance(document, dict) or not document.get("id"):
                                raise ValueError("Dify 未返回有效 document.id")
                            db.execute(sql.SQL(
                                "UPDATE {} SET fk_r8p0_sync_kb=%s WHERE fid=%s"
                            ).format(table), (SYNCED, fid))
                        outcome["synced"] += 1
                        logger.info("fid=%s 已提交知识库，Dify 将异步建立索引", fid)
                    except (requests.RequestException, ValueError, psycopg.Error) as exc:
                        outcome["failed"] += 1
                        logger.error("fid=%s 同步失败，保留待同步状态：%s", fid, exc)
    logger.info("知识库同步结束：成功=%d，失败=%d，跳过=%d",
                outcome["synced"], outcome["failed"], outcome["skipped"])
    return outcome


def count_unsynchronized(config_path: str | Path | None = None) -> int:
    """Count rows whose knowledge-base status is not 是."""
    config = load(config_path)["database"]
    table = sql.Identifier(config["schema"], config["table"])
    with psycopg.connect(host=config["host"], port=config["port"],
                         dbname=config["database"], user=config["user"],
                         password=config.get("password", ""), connect_timeout=5) as db:
        return db.execute(sql.SQL(
            "SELECT COUNT(*) FROM {} WHERE COALESCE(fk_r8p0_sync_kb, '') <> %s"
        ).format(table), (SYNCED,)).fetchone()[0]


def mark_all_synced(config_path: str | Path | None = None) -> int:
    """Mark every row as synchronized without contacting Dify.

    This is intended for one-time migration of deployments created before the
    status semantics were corrected, so previously submitted cases are not sent
    again.
    """
    config = load(config_path)["database"]
    table = sql.Identifier(config["schema"], config["table"])
    with psycopg.connect(host=config["host"], port=config["port"],
                         dbname=config["database"], user=config["user"],
                         password=config.get("password", ""), connect_timeout=5) as db:
        cursor = db.execute(sql.SQL(
            "UPDATE {} SET fk_r8p0_sync_kb=%s WHERE COALESCE(fk_r8p0_sync_kb, '') <> %s"
        ).format(table), (SYNCED, SYNCED))
        return cursor.rowcount


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将数据库待同步案例提交到 Dify 知识库")
    parser.add_argument("--dry-run", action="store_true", help="只查询待同步数量")
    parser.add_argument("--limit", type=int, help="本次处理上限（默认处理全部待同步案例）")
    parser.add_argument("--database-config", help="包含 database 和 dify 的 JSON 配置路径")
    parser.add_argument("--no-disable-old", action="store_true",
                        help="同步前不禁用知识库中的旧文档")
    parser.add_argument("--mark-synced", action="store_true",
                        help="仅把全部案例标记为已同步（用于迁移旧状态）")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        if args.mark_synced:
            if args.dry_run:
                count = count_unsynchronized(args.database_config)
                logger.info("待标记 %d 条", count)
            else:
                count = mark_all_synced(args.database_config)
                logger.info("已标记 %d 条为已同步", count)
            return 0
        outcome = synchronize(args.database_config, dry_run=args.dry_run, limit=args.limit,
                            disable_old=not args.no_disable_old)
    except Exception as exc:
        logger.error("知识库同步失败：%s", exc)
        return 1
    return 1 if outcome["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
