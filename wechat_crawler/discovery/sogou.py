# -*- coding: utf-8 -*-
"""搜狗微信搜索文章发现器"""

import re
import sys
import time
from pathlib import Path
from typing import List
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import requests

from .base import BaseDiscovery, CandidateURL
from ..config import SOGOU_WEIXIN_URL

# HEADERS 和 TIMEOUT 从主 config 导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import HEADERS, TIMEOUT


WECHAT_HOST = "mp.weixin.qq.com"
STABLE_QUERY_KEYS = ("__biz", "mid", "idx", "sn")


class SogouDiscovery(BaseDiscovery):
    """通过搜狗微信搜索发现文章"""

    def __init__(self, max_pages: int = 10):
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def discover(self, account_name: str, aliases: List[str]) -> List[CandidateURL]:
        """搜索所有别名，解析真实微信文章 URL 后收集候选。"""
        candidates = []
        seen_urls = set()

        for alias in aliases:
            for page in range(1, self.max_pages + 1):
                search_url = "{}?type=2&query={}&page={}".format(
                    SOGOU_WEIXIN_URL, quote(alias), page
                )
                try:
                    resp = self.session.get(search_url, timeout=TIMEOUT)
                    resp.encoding = "utf-8"

                    if resp.status_code != 200:
                        print("    搜狗搜索返回状态 {}: {}".format(resp.status_code, alias))
                        break

                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    txt_boxes = soup.select("div.txt-box")

                    if not txt_boxes:
                        print("    搜狗搜索未返回文章列表: {} 第 {} 页".format(alias, page))
                        break

                    for box in txt_boxes:
                        link = box.find("a")
                        if not link:
                            continue
                        href = link.get("href", "")
                        title = link.get_text(strip=True)

                        if not href or not title:
                            continue

                        # 拼接搜狗完整跳转 URL，再解析为真实微信文章地址。
                        if href.startswith("/"):
                            href = "https://weixin.sogou.com" + href

                        article_url = self._resolve_article_url(href)
                        candidate_url = article_url or href
                        # 解析失败时用标题去重，避免三个别名产生同文重复记录。
                        key = article_url or ("unresolved", re.sub(r"\s+", " ", title).strip())
                        if key not in seen_urls:
                            seen_urls.add(key)
                            candidates.append(CandidateURL(
                                account_name=account_name,
                                url=candidate_url,
                                source="sogou",
                                title=title,
                            ))

                    time.sleep(1)

                except Exception as e:
                    print("    搜狗搜索失败 ({}): {}".format(alias, e))
                    break

            time.sleep(2)

        return candidates

    def discover_with_browser(self, page, context, account_name: str, aliases: List[str]):
        """使用 Playwright 浏览器搜索，作为 requests 发现失败时的兜底。"""
        candidates = []
        seen_keys = set()
        for alias in aliases:
            for page_number in range(1, self.max_pages + 1):
                search_url = "{}?type=2&query={}&page={}".format(
                    SOGOU_WEIXIN_URL, quote(alias), page_number
                )
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1500)
                    rows = page.evaluate("""() => Array.from(document.querySelectorAll('div.txt-box')).map(box => {
                        const link = box.querySelector('a[href]');
                        return link ? {href: link.href, title: (link.innerText || '').trim()} : null;
                    }).filter(Boolean)""")
                    if not rows:
                        print("    浏览器搜索未返回文章列表: {} 第 {} 页".format(alias, page_number))
                        break

                    for row in rows:
                        href = row.get("href", "")
                        title = row.get("title", "")
                        if not href or not title:
                            continue
                        try:
                            response = context.request.get(href, max_redirects=5, timeout=30000)
                            resolved = self._normalize_article_url(response.url)
                        except Exception:
                            resolved = ""
                        candidate_url = resolved or href
                        key = resolved or ("unresolved", re.sub(r"\s+", " ", title).strip())
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        candidates.append(CandidateURL(
                            account_name=account_name,
                            url=candidate_url,
                            source="sogou-browser",
                            title=title,
                        ))
                except Exception as exc:
                    print("    浏览器搜索失败 ({}): {}".format(alias, exc))
                    break
        return candidates

    def _resolve_article_url(self, url: str) -> str:
        """跟随搜狗跳转并返回稳定的 mp.weixin.qq.com 文章 URL。"""
        try:
            response = self.session.head(
                url,
                allow_redirects=True,
                timeout=min(TIMEOUT, 10),
            )
            final_url = response.url
            response.close()
            if not self._is_wechat_article_url(final_url):
                response = self.session.get(
                    url,
                    allow_redirects=True,
                    timeout=min(TIMEOUT, 10),
                    stream=True,
                )
                final_url = response.url
                response.close()
        except requests.RequestException as exc:
            print("    跳转解析失败: {}".format(exc))
            return ""

        return self._normalize_article_url(final_url)

    @staticmethod
    def _normalize_article_url(final_url: str) -> str:
        parts = urlsplit(final_url)
        if not SogouDiscovery._is_wechat_article_url(final_url):
            return ""
        query = parse_qsl(parts.query, keep_blank_values=True)
        stable_query = [(key, value) for key, value in query if key in STABLE_QUERY_KEYS]
        normalized_query = urlencode(stable_query) if stable_query else parts.query
        return urlunsplit(("https", WECHAT_HOST, parts.path, normalized_query, ""))

    @staticmethod
    def _is_wechat_article_url(url: str) -> bool:
        parts = urlsplit(url)
        return parts.netloc.lower() == WECHAT_HOST and parts.path.startswith("/s")
