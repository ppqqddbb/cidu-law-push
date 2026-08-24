#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通过搜狗微信搜索爬取指定公众号的文章。
搜狗微信搜索可以搜索公众号名称，返回该公众号的文章列表。
"""

import argparse
import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import WECHAT_ARTICLES, HEADERS, TIMEOUT


# 搜狗微信搜索 URL
SOGOU_WEIXIN_URL = "https://weixin.sogou.com/weixin"

# 日期正则
DATE_RE = re.compile(
    r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
    r"|(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
)


def parse_args():
    parser = argparse.ArgumentParser(description="通过搜狗微信搜索爬取公众号文章")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD（包含）")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD（包含）")
    parser.add_argument("--out", default="wechat_titles_sogou.csv")
    parser.add_argument("--max-pages", type=int, default=20, help="每个公众号最多搜索页数")
    return parser.parse_args()


def parse_day(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"日期格式错误: {value}，应为 YYYY-MM-DD") from exc


def parse_date_text(value, today=None):
    """解析日期文本，返回 date 对象"""
    if not value:
        return None
    today = today or date.today()
    value = value.replace("-", "/")
    match = DATE_RE.search(value)
    if not match:
        return None
    try:
        if match.group(1):
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return date(today.year, int(match.group(4)), int(match.group(5)))
    except ValueError:
        return None


def parse_relative_time(time_text):
    """解析相对时间（如 '3小时前'、'昨天'）"""
    now = datetime.now()
    if '分钟前' in time_text or '小时前' in time_text:
        return now.strftime("%Y-%m-%d")
    elif '昨天' in time_text:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    elif '前天' in time_text:
        return (now - timedelta(days=2)).strftime("%Y-%m-%d")
    elif '天前' in time_text:
        match = re.search(r'(\d+)天前', time_text)
        if match:
            return (now - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d")
    return ""


def search_sogou_weixin(keyword, max_pages=20, timeout=15):
    """通过搜狗微信搜索获取文章列表"""
    items = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max_pages + 1):
        search_url = f"{SOGOU_WEIXIN_URL}?type=2&query={quote(keyword)}&page={page}"
        try:
            resp = session.get(search_url, timeout=timeout)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print(f"  搜索失败: {keyword}, 页码: {page}, 状态码: {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            txt_boxes = soup.select('div.txt-box')

            if not txt_boxes:
                print(f"  第 {page} 页无文章，停止")
                break

            print(f"  第 {page} 页找到 {len(txt_boxes)} 个文章")

            for box in txt_boxes:
                try:
                    title_link = box.find('a')
                    if not title_link:
                        continue

                    title = title_link.get_text(strip=True)
                    article_url = title_link.get('href', '')

                    if not title or not article_url:
                        continue

                    # 提取时间
                    date_text = ""
                    time_script = box.find('script', string=re.compile(r'timeConvert'))
                    if time_script:
                        match = re.search(r"timeConvert\('(\d+)'\)", time_script.string)
                        if match:
                            timestamp = int(match.group(1))
                            date_text = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

                    if not date_text:
                        time_elem = box.find('span', class_='s2')
                        if time_elem:
                            time_text = time_elem.get_text(strip=True)
                            # 先尝试解析为绝对日期
                            parsed = parse_date_text(time_text)
                            if parsed:
                                date_text = parsed.strftime("%Y-%m-%d")
                            else:
                                # 再尝试解析相对时间
                                date_text = parse_relative_time(time_text)

                    # 获取真实微信链接
                    real_url = article_url
                    if article_url.startswith('/'):
                        article_url = f"https://weixin.sogou.com{article_url}"
                    try:
                        resp_head = session.head(article_url, allow_redirects=True, timeout=10)
                        real_url = resp_head.url
                    except:
                        pass

                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": real_url,
                        "keyword": keyword,
                    })

                except Exception as e:
                    print(f"  解析文章失败: {e}")
                    continue

            time.sleep(1)

        except Exception as e:
            print(f"  请求失败: {e}")
            break

    return items


def main():
    args = parse_args()
    end = parse_day(args.end, date.today())
    start = parse_day(args.start, end - timedelta(days=7))
    if start > end:
        raise SystemExit("--start 不能晚于 --end")

    output_path = Path(args.out)
    all_rows = []

    for article in WECHAT_ARTICLES:
        account = article["account"]
        print(f"\n搜索公众号: {account}")

        # 使用公众号名称搜索
        items = search_sogou_weixin(account, max_pages=args.max_pages)
        print(f"  共找到 {len(items)} 篇文章")

        # 按日期筛选
        for item in items:
            item_date = parse_date_text(item["date"])
            if item_date and start <= item_date <= end:
                all_rows.append({
                    "title": item["title"],
                    "source": account,
                    "date": item["date"],
                    "url": item["url"],
                    "summary": "",
                })
            else:
                # 调试：显示前5个未通过的日期
                if len([x for x in items if x["title"] == item["title"]]) <= 5:
                    print(f"    跳过: {item['title'][:30]}... 日期: {item['date']} -> {item_date}")

        time.sleep(2)

    # 去重
    unique = {}
    for row in all_rows:
        unique[(row["source"], row["url"])] = row
    rows = sorted(unique.values(), key=lambda item: (item["date"] or "", item["source"]), reverse=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(("标题", "来源", "时间", "摘要", "链接"))
        for row in rows:
            writer.writerow((row["title"], row["source"], row["date"], row["summary"], row["url"]))

    print(f"\n已导出 {len(rows)} 条: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("已取消")
