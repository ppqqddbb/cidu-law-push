# -*- coding: utf-8 -*-
"""SQLite 存储模块 - URL 队列和文章数据"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..discovery.base import CandidateURL


class WechatStorage:
    """SQLite 存储管理"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS article_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    source TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    discovered_at TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT DEFAULT '',
                    publish_time TEXT DEFAULT '',
                    author TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    images TEXT DEFAULT '',
                    verified INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.commit()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def add_candidates(self, candidates: List[CandidateURL]):
        """添加候选 URL 到队列"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            for c in candidates:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO article_urls "
                        "(account_name, url, source, title, discovered_at, status) "
                        "VALUES (?, ?, ?, ?, ?, 'pending')",
                        (c.account_name, c.url, c.source, c.title, now),
                    )
                except sqlite3.IntegrityError:
                    pass
                conn.execute(
                    "UPDATE article_urls SET account_name = ?, source = ?, title = ?, "
                    "status = 'pending' WHERE url = ? AND status = 'invalid_url'",
                    (c.account_name, c.source, c.title, c.url),
                )
            conn.commit()

    def reject_non_wechat_candidates(self, account_names: Optional[List[str]] = None):
        """停用历史遗留的搜狗跳转地址，避免它们再次进入采集阶段。"""
        with self._connect() as conn:
            query = (
                "UPDATE article_urls SET status = 'invalid_url' "
                "WHERE status IN ('pending', 'fetching') "
                "AND url NOT LIKE 'https://mp.weixin.qq.com/s%'"
            )
            params = []
            if account_names is not None:
                names = list(account_names)
                if not names:
                    return
                placeholders = ", ".join("?" for _ in names)
                query += " AND account_name IN ({})".format(placeholders)
                params.extend(names)
            conn.execute(query, params)
            conn.commit()

    def get_pending(self, limit: int = 100, account_names: Optional[List[str]] = None) -> List[dict]:
        """获取待处理的候选 URL，可按公众号范围过滤。"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM article_urls WHERE status = 'pending'"
            params = []
            if account_names is not None:
                names = list(account_names)
                if not names:
                    return []
                placeholders = ", ".join("?" for _ in names)
                query += " AND account_name IN ({})".format(placeholders)
                params.extend(names)
            query += " LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def update_url_status(self, url: str, status: str):
        """更新 URL 状态"""
        with self._connect() as conn:
            conn.execute(
                "UPDATE article_urls SET status = ? WHERE url = ?",
                (status, url),
            )
            conn.commit()

    def save_article(self, article: dict, account_name: str):
        """保存已验证的文章"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        images_str = ",".join(article.get("images", []))
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO articles "
                    "(account_name, url, title, publish_time, author, content, images, verified, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                    (
                        account_name,
                        article["url"],
                        article.get("title", ""),
                        article.get("publish_time", ""),
                        article.get("author", ""),
                        article.get("content", ""),
                        images_str,
                        now,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass

    def get_all_articles(self, account_names: Optional[List[str]] = None) -> List[dict]:
        """获取已验证的文章，可按公众号范围过滤。"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM articles WHERE verified = 1"
            params = []
            if account_names is not None:
                names = list(account_names)
                if not names:
                    return []
                placeholders = ", ".join("?" for _ in names)
                query += " AND account_name IN ({})".format(placeholders)
                params.extend(names)
            query += " ORDER BY publish_time DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_pending_count(self, account_names: Optional[List[str]] = None) -> int:
        """获取待处理数量，可按公众号范围过滤。"""
        with self._connect() as conn:
            query = "SELECT COUNT(*) FROM article_urls WHERE status = 'pending'"
            params = []
            if account_names is not None:
                names = list(account_names)
                if not names:
                    return 0
                placeholders = ", ".join("?" for _ in names)
                query += " AND account_name IN ({})".format(placeholders)
                params.extend(names)
            row = conn.execute(query, params).fetchone()
            return row[0] if row else 0
