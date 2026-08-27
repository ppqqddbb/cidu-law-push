#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export filtered article metadata collected by wechat-spider.

The upstream project stores article-list data in MySQL. This adapter keeps the
database dependency out of the crawler and only exports the fields needed by
Law-Push: title, account, publish time, URL and digest.
"""

import argparse
import csv
import os
from datetime import datetime, timedelta

import pymysql


ACCOUNTS = (
    "山东高法",
)
ACCOUNT_PATTERNS = (
    "%山东高法%",
)


def parse_args():
    parser = argparse.ArgumentParser(description="导出 wechat-spider 中指定公众号的文章标题")
    parser.add_argument("--start", help="开始日期，YYYY-MM-DD；默认最近 7 天")
    parser.add_argument("--end", help="结束日期，YYYY-MM-DD；默认今天")
    parser.add_argument("--out", default="wechat_titles.csv")
    parser.add_argument("--host", default=os.getenv("WECHAT_DB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WECHAT_DB_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("WECHAT_DB_USER", "root"))
    parser.add_argument("--password", default=os.getenv("WECHAT_DB_PASSWORD", "root"))
    parser.add_argument("--database", default=os.getenv("WECHAT_DB_NAME", "test"))
    return parser.parse_args()


def main():
    args = parse_args()
    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
    start = (
        datetime.strptime(args.start, "%Y-%m-%d")
        if args.start
        else end - timedelta(days=7)
    )
    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user, password=args.password,
        database=args.database, charset="utf8mb4",
        # 导出本机/局域网 MySQL 数据，不需要 TLS；避免 Windows 证书库异常
        # （ASN1: NOT_ENOUGH_DATA）导致 PyMySQL 在创建 SSL 上下文时失败。
        ssl_disabled=True,
    )
    sql = """
        SELECT COALESCE(a.account, l.__biz) AS account,
               l.title, l.url, l.publish_time, l.digest
        FROM wechat_article_list AS l
        LEFT JOIN wechat_account AS a ON a.__biz = l.__biz
        WHERE (COALESCE(a.account, '') IN (%s)
           OR COALESCE(a.account, '') LIKE %s)
          AND l.publish_time >= %s
          AND l.publish_time < %s
        ORDER BY l.publish_time DESC
    """
    params = (*ACCOUNTS, *ACCOUNT_PATTERNS, start, end + timedelta(days=1))
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    finally:
        conn.close()

    with open(args.out, "w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(("标题", "来源", "时间", "摘要", "链接"))
        for account, title, url, publish_time, digest in rows:
            writer.writerow((title or "", account or "", publish_time or "", digest or "", url or ""))
    print(f"已导出 {len(rows)} 条: {args.out}")


if __name__ == "__main__":
    main()
