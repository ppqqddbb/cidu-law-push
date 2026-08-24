# -*- coding: utf-8 -*-
"""
微信公众号文章采集器 - 主爬虫编排器

架构:
  Law-Push → WeChatCrawler
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
  Article Discovery    Article Fetcher
  (搜狗等搜索引擎)      (Playwright 访问文章页)
        │                   │
        └─────────┬─────────┘
                  ▼
            URL 去重 + 时间过滤
                  │
                  ▼
            公众号识别验证
                  │
                  ▼
            CSV / SQLite 输出
"""

import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .config import (
    load_accounts, ensure_dirs, WECHAT_ARTICLE_RE,
    BROWSER_PROFILE_DIR, DB_PATH, OUTPUT_CSV,
)
from .discovery.base import CandidateURL
from .discovery.sogou import SogouDiscovery
from .browser.playwright_manager import PlaywrightManager
from .fetcher.wechat_article import WechatArticleFetcher
from .parser.article_parser import ArticleParser
from .storage.sqlite import WechatStorage


class WeChatCrawler:
    """微信公众号文章采集器"""

    def __init__(self, start_date: str = None, end_date: str = None,
                 max_pages: int = 10, headless: bool = False):
        self.end = self._parse_day(end_date, date.today())
        self.start = self._parse_day(start_date, self.end - timedelta(days=7))
        if self.start > self.end:
            raise ValueError("--start 不能晚于 --end")

        self.max_pages = max_pages
        self.headless = headless

        ensure_dirs()

        self.accounts = load_accounts()
        self.account_names = [account["name"] for account in self.accounts]
        self.parser = ArticleParser(self.accounts)
        self.storage = WechatStorage(str(DB_PATH))
        self.discovery = SogouDiscovery(max_pages=max_pages)

    @staticmethod
    def _parse_day(value, default):
        if not value:
            return default
        return datetime.strptime(value, "%Y-%m-%d").date()

    def run(self):
        """执行完整采集流程"""
        print("微信公众号文章采集器")
        print("时间范围: {} 至 {}".format(self.start, self.end))
        print("目标公众号: {} 个".format(len(self.accounts)))
        print("=" * 60)

        # 第一阶段：文章发现（多源）
        print("\n[阶段1] 文章发现...")
        # 清理上一轮遗留的搜狗跳转候选；本轮新发现的候选随后再入库。
        self.storage.reject_non_wechat_candidates(self.account_names)
        for acc in self.accounts:
            name = acc["name"]
            aliases = acc.get("aliases", [name])
            print("  发现: {} (别名: {})".format(name, ", ".join(aliases)))
            candidates = self.discovery.discover(name, aliases)
            if not candidates:
                print("    requests 未发现结果，切换到浏览器搜索兜底...")
                with PlaywrightManager(str(BROWSER_PROFILE_DIR), headless=self.headless) as discovery_browser:
                    discovery_page = discovery_browser.new_page()
                    try:
                        candidates = self.discovery.discover_with_browser(
                            discovery_page,
                            discovery_browser.context,
                            name,
                            aliases,
                        )
                    finally:
                        discovery_page.close()
            print("    发现 {} 个候选 URL".format(len(candidates)))
            self.storage.add_candidates(candidates)

        pending = self.storage.get_pending_count(self.account_names)
        print("  待处理: {} 个 URL".format(pending))

        # 第二阶段：文章采集 + 验证
        print("\n[阶段2] 文章采集与验证...")
        verified_count = 0

        with PlaywrightManager(str(BROWSER_PROFILE_DIR), headless=self.headless) as browser:
            fetcher = WechatArticleFetcher(browser)

            batch = self.storage.get_pending(limit=200, account_names=self.account_names)
            for item in batch:
                url = item["url"]
                account_name = item["account_name"]
                print("  采集: {} ...".format(url[:80]))

                self.storage.update_url_status(url, "fetching")

                article = fetcher.fetch(url)
                if not article:
                    self.storage.update_url_status(url, "failed")
                    continue

                # 公众号识别验证
                matched_name = self.parser.match_account(article.get("account", ""))
                if not matched_name:
                    print("    公众号不匹配: {} (页面: {})".format(
                        account_name, article.get("account", "")))
                    self.storage.update_url_status(url, "rejected")
                    continue

                # 时间过滤（以文章页面发布时间为准）
                pub_time = article.get("publish_time", "")
                if not self.parser.is_in_range(pub_time, self.start, self.end):
                    print("    时间不在范围内: {} ({})".format(pub_time, url[:60]))
                    self.storage.update_url_status(url, "out_of_range")
                    continue

                # 保存验证通过的文章
                self.storage.save_article(article, matched_name)
                self.storage.update_url_status(url, "verified")
                verified_count += 1
                print("    验证通过: {} ({})".format(article["title"][:40], pub_time))

                time.sleep(1)

        # 第三阶段：输出
        print("\n[阶段3] 输出结果...")
        self._export_csv()

        print("\n" + "=" * 60)
        print("采集完成! 验证通过 {} 条文章".format(verified_count))

    def _export_csv(self):
        """导出 CSV"""
        articles = self.storage.get_all_articles(self.account_names)
        if not articles:
            print("  无数据可导出")
            return

        with open(str(OUTPUT_CSV), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(("标题", "来源", "时间", "摘要", "链接"))
            for art in articles:
                writer.writerow((
                    art["title"],
                    art["account_name"],
                    art["publish_time"],
                    "",
                    art["url"],
                ))

        print("  已导出 {} 条: {}".format(len(articles), OUTPUT_CSV))
