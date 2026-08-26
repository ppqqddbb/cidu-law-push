# -*- coding: utf-8 -*-
"""
法律信息爬虫 - 爬取多个法律网站的最新法律信息
支持按时间范围筛选，输出格式化的法律信息
"""

import re
import json
import time
import ssl
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.ssl_ import create_urllib3_context
except ImportError:
    create_urllib3_context = None

from config import (
    HEADERS,
    TIMEOUT,
    DEFAULT_DAYS,
    LAW_OUTPUT_FILE,
    CASE_OUTPUT_FILE,
    SITES,
    COURT_CASE_SOURCE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SSLAdapter(HTTPAdapter):
    """自定义SSL适配器，解决某些网站的SSL握手问题"""
    def __init__(self, *args, **kwargs):
        self.ssl_context = None
        super().__init__(*args, **kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        if create_urllib3_context:
            # 创建最宽松的SSL上下文
            ctx = create_urllib3_context(
                ciphers='ALL:@SECLEVEL=0',
                ssl_version=ssl.PROTOCOL_TLSv1_2
            )
            # 移除所有不必要的SSL选项限制
            ctx.options &= ~ssl.OP_NO_SSLv3
            ctx.options &= ~ssl.OP_NO_TLSv1
            ctx.options &= ~ssl.OP_NO_TLSv1_1
            ctx.options &= ~ssl.OP_NO_TLSv1_2
            ctx.options &= ~ssl.OP_NO_TLSv1_3
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self.ssl_context = ctx
            kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


class LawCrawler:
    def __init__(self, days=None):
        self.days = days or DEFAULT_DAYS
        self.cutoff_date = datetime.now() - timedelta(days=self.days)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # 为npc.gov.cn添加SSL适配器
        self.session.mount("https://www.npc.gov.cn", SSLAdapter())
        self.results = []
        self.case_results = []

    def _fetch(self, url, encoding=None):
        """通用请求方法"""
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            if encoding:
                resp.encoding = encoding
            else:
                resp.encoding = resp.apparent_encoding
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning(f"请求失败: {url} -> {e}")
            return None

    def _browser_fetch(self, url):
        """可选的 JS 页面兜底；未安装 Playwright 时返回 None。"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent=HEADERS.get("User-Agent"),
                    locale="zh-CN",
                    ignore_https_errors=True,
                )
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
                page.wait_for_timeout(1000)
                html = page.content()
                browser.close()
                return html
        except Exception as exc:
            logger.warning(f"浏览器获取失败: {url} -> {exc}")
            return None

    def _parse_date(self, date_str):
        """解析日期字符串，返回 datetime 对象"""
        if not date_str:
            return None
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y.%m.%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _is_in_range(self, date_str):
        """判断日期是否在指定时间范围内"""
        dt = self._parse_date(date_str)
        if dt is None:
            return False
        return dt.date() >= self.cutoff_date.date()

    def _extract_date(self, text):
        """从列表项或详情页文本中提取常见中文/数字日期。"""
        if not text:
            return ""
        text = str(text)
        patterns = (
            r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?",
            r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
            r"(20\d{2})(\d{2})(\d{2})",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return datetime(
                        int(match.group(1)), int(match.group(2)), int(match.group(3))
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return ""



    # ==================== 国家法律法规数据库 ====================
    def crawl_flk_npc(self):
        """爬取国家法律法规数据库 - 通过 search/list API 获取完整法律法规列表"""
        logger.info("开始爬取: 国家法律法规数据库")
        site = SITES["flk_npc"]
        api_url = "https://flk.npc.gov.cn/law-search/search/list"
        items = []

        # 使用完整的搜索参数（从 JS 分析得到）
        payload = {
            "searchRange": 1,
            "sxrq": [],
            "gbrq": [],
            "searchType": 2,
            "sxx": [],
            "gbrqYear": [],
            "flfgCodeId": [],
            "zdjgCodeId": [],
            "searchContent": "",
            "page": 1,
            "size": 100,  # 获取前 100 条
        }

        try:
            resp = self.session.post(api_url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get("total", 0) > 0 and data.get("rows"):
                rows = data["rows"]
                logger.info(f"search/list API 返回 {len(rows)} 条数据（总计 {data['total']} 条）")
                logger.info(f"截止日期: {self.cutoff_date.strftime('%Y-%m-%d')}")

                for item_data in rows:
                    title = item_data.get("title", "")
                    pub_date = item_data.get("gbrq", "")  # 公布日期
                    bbbs = item_data.get("bbbs", "")  # 文档ID

                    # Debug: log first few items to see what dates we're getting
                    if len(items) < 3 or len(rows) - len(items) < 3:
                        logger.info(f"检查项目: title={title[:30]}, pub_date={pub_date}, parsed={self._parse_date(pub_date)}, in_range={self._is_in_range(pub_date)}")

                    if title and pub_date and self._is_in_range(pub_date):
                        detail_url = f"https://flk.npc.gov.cn/detail2.html?{bbbs}"
                        items.append({
                            "title": title,
                            "date": pub_date,
                            "url": detail_url,
                            "source": site["source_label"],
                        })
            else:
                logger.warning(f"API 返回数据为空: {data}")
        except Exception as e:
            logger.warning(f"请求 search/list API 失败: {e}")
            # fallback: 使用 aggregateData API（数据较少但更稳定）
            logger.info("尝试 fallback: aggregateData API")
            try:
                agg_url = "https://flk.npc.gov.cn/law-search/index/aggregateData"
                resp = self.session.get(agg_url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 200 and data.get("data") and data["data"].get("xfsd"):
                    for item_data in data["data"]["xfsd"]:
                        title = item_data.get("title", "")
                        pub_date = item_data.get("gbrq", "")
                        bbbs = item_data.get("bbbs", "")
                        if title and pub_date and self._is_in_range(pub_date):
                            detail_url = f"https://flk.npc.gov.cn/detail2.html?{bbbs}"
                            items.append({
                                "title": title,
                                "date": pub_date,
                                "url": detail_url,
                                "source": site["source_label"],
                            })
                    logger.info(f"aggregateData fallback: 获取 {len(items)} 条")
            except Exception as e2:
                logger.warning(f"aggregateData fallback 也失败: {e2}")

        # 去重
        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"国家法律法规数据库: 获取 {len(items)} 条")

    # ==================== 中国政府网·政策文件库 ====================
    def crawl_gov_cn(self):
        """爬取中国政府网·政策文件库 - 使用 JSON API"""
        logger.info("开始爬取: 中国政府网·政策文件库")
        site = SITES["gov_cn"]
        items = []

        # 使用 JSON API 获取数据
        json_url = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"
        try:
            resp = self.session.get(json_url, timeout=TIMEOUT)
            resp.encoding = "utf-8"
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, list):
                for item_data in data:
                    title = item_data.get("TITLE", "")
                    url = item_data.get("URL", "")
                    pub_date = item_data.get("DOCRELPUBTIME", "")
                    
                    if title and url and pub_date and self._is_in_range(pub_date):
                        items.append({
                            "title": title,
                            "date": pub_date,
                            "url": url,
                            "source": site["source_label"],
                        })
                logger.info(f"中国政府网: 从 JSON API 获取 {len(items)} 条")
            else:
                logger.warning(f"中国政府网 JSON API 返回数据格式异常: {type(data)}")
        except Exception as e:
            logger.warning(f"中国政府网 JSON API 请求失败: {e}")

        # 去重
        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"中国政府网: 获取 {len(items)} 条")

    # ==================== 中国人大网 ====================
    def crawl_npc_gov(self):
        """爬取中国人大网 - 只爬取立法、监督等法律内容"""
        logger.info("开始爬取: 中国人大网")
        site = SITES["npc_gov"]
        # 使用HTTP主页避免SSL握手失败
        page_url = "http://www.npc.gov.cn/npc/index.html"

        items = []
        html = self._fetch(page_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue
                                
                # 从URL或页面内容提取日期
                date_text = ""
                url_date_match = re.search(r"(\d{4})(\d{2})", href)
                if url_date_match:
                    date_text = f"{url_date_match.group(1)}-{url_date_match.group(2)}-01"

                parent = link.parent
                if not date_text and parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)

                if date_text and self._is_in_range(date_text):
                    # 相对于主页解析相对路径
                    full_url = urljoin(page_url, href)
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"中国人大网: 获取 {len(items)} 条")

    # ==================== 司法部 ====================
    def crawl_moj_gov(self):
        """爬取司法部 - 处理 JavaScript 重定向"""
        logger.info("开始爬取: 司法部")
        site = SITES["moj_gov"]
        
        # 司法部页面使用 JS 重定向，需要直接访问重定向后的 URL
        urls_to_try = [
            f"{site['base_url']}/pub/sfbgw/zwgk/zwgkxxgk/",  # 政务公开-信息公开
            f"{site['base_url']}/pub/sfbgw/gwxw/ttxw/",  # 新闻中心-头条新闻
        ]

        items = []
        for page_url in urls_to_try:
            html = self._fetch(page_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue

                parent = link.parent
                date_text = ""
                if parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)

                # 从URL提取日期
                if not date_text:
                    url_date_match = re.search(r"(\d{4})(\d{2})/t\d+_(\d+)", href)
                    if url_date_match:
                        date_text = f"{url_date_match.group(1)}-{url_date_match.group(2)}-{url_date_match.group(3)[:2]}"

                if date_text and self._is_in_range(date_text):
                    full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"司法部: 获取 {len(items)} 条")

    # ==================== 最高人民法院 ====================
    def crawl_court_case_77(self):
        """爬取最高人民法院审判栏目 77（指导案例/法律案例）并保存到 case.txt。"""
        logger.info(
            "开始爬取: "
            + " -> ".join(COURT_CASE_SOURCE.get("breadcrumb", []))
        )
        page_url = COURT_CASE_SOURCE["list_url"]
        html = self._fetch(page_url)
        if not html:
            logger.warning("最高人民法院案例栏目 77 获取失败")
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []
        seen = set()
        for link in soup.find_all("a", href=True):
            title = " ".join(link.get_text(" ", strip=True).split())
            href = link.get("href", "").strip()
            if not title or len(title) < 4 or not href:
                continue
            if href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)
            if parsed.hostname and parsed.hostname.lower() not in {
                "court.gov.cn",
                "www.court.gov.cn",
            }:
                continue
            # 排除栏目页、分页和导航链接，只保留详情页。
            if "/shenpan/gengduo/" in parsed.path.lower():
                continue

            container = link.find_parent(["li", "tr", "article", "dd", "div"])
            context = container.get_text(" ", strip=True) if container else title
            date_text = self._extract_date(context) or self._extract_date(href)

            if not date_text:
                detail_html = self._fetch(full_url)
                date_text = self._extract_date(detail_html or "")
            if not date_text or not self._is_in_range(date_text):
                continue

            key = (title, full_url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "title": title,
                    "date": date_text,
                    "url": full_url,
                    "source": COURT_CASE_SOURCE["source_label"],
                }
            )

        self.case_results = items
        # 保留在内存总结果中，写入文件时会与法规结果分流。
        existing = {(item.get("title"), item.get("url")) for item in self.results}
        for item in items:
            if (item["title"], item["url"]) not in existing:
                self.results.append(item)
        logger.info(f"最高人民法院案例栏目 77: 获取 {len(items)} 条")
        return items

    def crawl_legal_portal(self, site_key):
        """抓取威科先行、北大法宝等门户公开可访问的法律信息。"""
        site = SITES[site_key]
        logger.info(f"开始爬取: {site['source_label']}")
        items = []
        seen = set()
        entry_urls = site.get("entry_urls", [site["base_url"]])
        allowed_hosts = {host.lower() for host in site.get("allowed_hosts", [])}
        keywords = re.compile(
            r"法律|法规|司法解释|案例|裁判|政策|规章|合规|解读|通知|公告|判决|仲裁",
            re.I,
        )

        for page_url in entry_urls:
            html = self._fetch(page_url)
            if not html:
                html = self._browser_fetch(page_url)
            if not html:
                logger.warning(f"{site['source_label']}: 入口页面不可访问，可能需要登录")
                continue
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            if not links:
                rendered_html = self._browser_fetch(page_url)
                if rendered_html:
                    soup = BeautifulSoup(rendered_html, "html.parser")
                    links = soup.find_all("a", href=True)
            for link in links[:300]:
                title = " ".join(link.get_text(" ", strip=True).split())
                href = link.get("href", "").strip()
                if not title or len(title) < 6 or not href:
                    continue
                if href.startswith(("#", "javascript:", "mailto:")):
                    continue
                full_url = urljoin(page_url, href)
                parsed = urlparse(full_url)
                if parsed.scheme not in ("http", "https"):
                    continue
                if allowed_hosts and parsed.hostname and parsed.hostname.lower() not in allowed_hosts:
                    continue
                if full_url.rstrip("/") == page_url.rstrip("/"):
                    continue
                if re.search(r"登录|注册|首页|关于我们|联系我们|帮助中心|下载|客服", title):
                    continue

                parent = link.find_parent(["li", "article", "tr", "dd", "section"])
                context = parent.get_text(" ", strip=True) if parent else title
                date_text = self._extract_date(context) or self._extract_date(href)
                if not date_text and not keywords.search(title):
                    continue
                if not date_text:
                    # 门户首页经常只显示标题，日期位于详情页；仅对疑似文章链接补取。
                    detail_html = self._fetch(full_url)
                    date_text = self._extract_date(detail_html or "")
                if not date_text or not self._is_in_range(date_text):
                    continue

                key = (title, full_url)
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    }
                )

        existing = {(item.get("title"), item.get("url")) for item in self.results}
        for item in items:
            if (item["title"], item["url"]) not in existing:
                self.results.append(item)
        logger.info(f"{site['source_label']}: 获取 {len(items)} 条")
        return items

    def crawl_court_gov(self):
        """爬取最高人民法院 - 只爬取司法解释、典型案例等法律内容"""
        logger.info("开始爬取: 最高人民法院")
        site = SITES["court_gov"]
        
        # 只爬取法律相关栏目
        urls_to_try = [
            f"{site['base_url']}/zixun/gengduo/23.html",  # 司法解释
            f"{site['base_url']}/zixun/gengduo/25.html",  # 司法文件
            f"{site['base_url']}/zixun/gengduo/26.html",  # 工作报告
        ]

        items = []

        # 爬取法律相关栏目
        for page_url in urls_to_try:
            html = self._fetch(page_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue
                if "xiangqing" not in href:
                    continue

                parent = link.parent
                date_text = ""
                if parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)

                # 尝试从详情页获取日期
                if not date_text and href:
                    detail_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    detail_html = self._fetch(detail_url)
                    if detail_html:
                        detail_soup = BeautifulSoup(detail_html, "html.parser")
                        date_elem = detail_soup.find(string=re.compile(r"\d{4}年\d{2}月\d{2}日"))
                        if date_elem:
                            match = re.search(r"(\d{4}年\d{2}月\d{2}日)", date_elem)
                            if match:
                                date_text = match.group(1)

                if date_text and self._is_in_range(date_text):
                    full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"最高人民法院: 获取 {len(items)} 条")

    # ==================== 最高人民检察院 ====================
    def crawl_spp_gov(self):
        """爬取最高人民检察院"""
        logger.info("开始爬取: 最高人民检察院")
        site = SITES["spp_gov"]
        urls_to_try = [
            f"{site['base_url']}/spp/tt/",  # 头条
            f"{site['base_url']}/spp/gzbg/",  # 工作报告
        ]

        items = []
        for page_url in urls_to_try:
            html = self._fetch(page_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            # 查找所有链接
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue
                
                # 只处理包含具体内容的链接
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                
                # 从URL或父元素提取日期
                date_text = ""
                parent = link.parent
                if parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)
                
                # 从URL提取日期
                if not date_text:
                    url_date_match = re.search(r"/(\d{4})(\d{2})/", href)
                    if url_date_match:
                        date_text = f"{url_date_match.group(1)}-{url_date_match.group(2)}-01"

                if date_text and self._is_in_range(date_text):
                    full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"最高人民检察院: 获取 {len(items)} 条")

    # ==================== 中国裁判文书网 ====================
    def crawl_wenshu_court(self):
        """爬取中国裁判文书网"""
        logger.info("开始爬取: 中国裁判文书网")
        site = SITES["wenshu_court"]
        
        # 裁判文书网使用API接口
        api_url = f"{site['base_url']}/website/parse/rest.q4c9e2a7f6b8d5f3a1e0c9b8d7f6e5a4"
        
        items = []
        try:
            # 尝试获取最新文书列表
            page_url = f"{site['base_url']}/website/parse/rest.q4c9e2a7f6b8d5f3a1e0c9b8d7f6e5a4"
            html = self._fetch(page_url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                links = soup.find_all("a", href=True)
                for link in links:
                    title = link.get_text(strip=True)
                    href = link.get("href", "")
                    if not title or len(title) < 4:
                        continue

                    parent = link.parent
                    date_text = ""
                    if parent:
                        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                        if date_match:
                            date_text = date_match.group(1)

                    if date_text and self._is_in_range(date_text):
                        full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                        items.append({
                            "title": title,
                            "date": date_text,
                            "url": full_url,
                            "source": site["source_label"],
                        })
        except Exception as e:
            logger.warning(f"中国裁判文书网爬取失败: {e}")

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"中国裁判文书网: 获取 {len(items)} 条")

    # ==================== 最高人民法院司法案例研究院 ====================
    def crawl_court_research(self):
        """爬取最高人民法院司法案例研究院"""
        logger.info("开始爬取: 最高人民法院司法案例研究院")
        site = SITES["court_research"]
        
        # 案例研究院在court.gov.cn下
        page_url = f"{site['base_url']}/zixun/gengduo/24.html"  # 典型案例
        
        items = []
        html = self._fetch(page_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue
                if "xiangqing" not in href:
                    continue

                parent = link.parent
                date_text = ""
                if parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)

                if date_text and self._is_in_range(date_text):
                    full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"最高人民法院司法案例研究院: 获取 {len(items)} 条")

    # ==================== 天平阳光 ====================
    def crawl_tianping(self):
        """爬取天平阳光"""
        logger.info("开始爬取: 天平阳光")
        site = SITES["tianping"]
        
        # 天平阳光是最高法的综合资讯平台
        page_url = site["base_url"]
        
        items = []
        html = self._fetch(page_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue
                
                # 只处理包含具体内容的链接
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                
                # 从URL或父元素提取日期
                date_text = ""
                parent = link.parent
                if parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)
                
                # 从URL提取日期
                if not date_text:
                    url_date_match = re.search(r"/(\d{4})(\d{2})/", href)
                    if url_date_match:
                        date_text = f"{url_date_match.group(1)}-{url_date_match.group(2)}-01"

                if date_text and self._is_in_range(date_text):
                    full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"天平阳光: 获取 {len(items)} 条")

    # ==================== 中国普法 ====================
    def crawl_china_pufa(self):
        """爬取中国普法"""
        logger.info("开始爬取: 中国普法")
        site = SITES["china_pufa"]
        
        # 中国普法在司法部网站下
        page_url = f"{site['base_url']}/pub/sfbgw/gwxw/ttxw/"
        
        items = []
        html = self._fetch(page_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or len(title) < 4:
                    continue

                parent = link.parent
                date_text = ""
                if parent:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                    if date_match:
                        date_text = date_match.group(1)

                # 从URL提取日期
                if not date_text:
                    url_date_match = re.search(r"(\d{4})(\d{2})/t\d+_(\d+)", href)
                    if url_date_match:
                        date_text = f"{url_date_match.group(1)}-{url_date_match.group(2)}-{url_date_match.group(3)[:2]}"

                if date_text and self._is_in_range(date_text):
                    full_url = urljoin(site["base_url"], href) if href.startswith("/") else href
                    items.append({
                        "title": title,
                        "date": date_text,
                        "url": full_url,
                        "source": site["source_label"],
                    })

        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)

        logger.info(f"中国普法: 获取 {len(items)} 条")

    # ==================== 微信公众号（通过搜狗微信搜索） ====================
    def crawl_wechat_accounts(self):
        """通过搜狗微信搜索爬取公众号文章"""
        logger.info("开始爬取: 微信公众号（搜狗微信搜索）")
        items = []
        
        for account_name, config in WECHAT_ACCOUNTS.items():
            keywords = config.get("keywords", [account_name])
            source_label = config.get("source_label", account_name)
            
            logger.info(f"搜索公众号: {account_name} (关键词: {keywords})")
            
            for keyword in keywords:
                # 通过搜狗微信搜索获取文章
                search_items = self._search_sogou_weixin(keyword, source_label)
                items.extend(search_items)
                time.sleep(1)  # 避免请求过快
        
        # 去重
        seen = set()
        for item in items:
            key = item["title"]
            if key not in seen:
                seen.add(key)
                self.results.append(item)
        
        logger.info(f"微信公众号: 获取 {len(items)} 条")
    
    def _search_sogou_weixin(self, keyword, source_label):
        """通过搜狗微信搜索获取文章，支持分页"""
        items = []
        max_pages = 50  # 搜狗微信搜索最多支持50页
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://weixin.sogou.com/',
        }
        
        # 搜狗微信搜索不是按时间排序，需要遍历所有页面
        for page in range(1, max_pages + 1):
            # 构建搜索URL，添加分页参数
            base_url = SOGOU_WEIXIN["base_url"]
            search_type = SOGOU_WEIXIN["type"]
            search_url = f"{base_url}?type={search_type}&query={keyword}&page={page}"
            
            try:
                resp = self.session.get(search_url, headers=headers, timeout=TIMEOUT)
                resp.encoding = 'utf-8'
                
                if resp.status_code != 200:
                    logger.warning(f"搜狗微信搜索失败: {keyword}, 页码: {page}, 状态码: {resp.status_code}")
                    break
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 查找文章列表
                txt_boxes = soup.select('div.txt-box')
                
                if not txt_boxes:
                    logger.info(f"  第 {page} 页无文章，停止分页")
                    break
                
                logger.info(f"  第 {page} 页找到 {len(txt_boxes)} 个文章容器")
                
                page_valid_count = 0
                
                for box in txt_boxes:
                    try:
                        # 提取标题和链接
                        title_link = box.find('a')
                        if not title_link:
                            continue
                        
                        title = title_link.get_text(strip=True)
                        article_url = title_link.get('href', '')
                        
                        if not title or not article_url:
                            continue
                        
                        # 提取时间戳 - 从 timeConvert('timestamp') 中提取
                        date_text = ""
                        time_script = box.find('script', string=re.compile(r'timeConvert'))
                        if time_script:
                            match = re.search(r"timeConvert\('(\d+)'\)", time_script.string)
                            if match:
                                timestamp = int(match.group(1))
                                dt = datetime.fromtimestamp(timestamp)
                                date_text = dt.strftime("%Y-%m-%d")
                        
                        # 如果没有找到时间戳，尝试从 span.s2 中提取
                        if not date_text:
                            time_elem = box.find('span', class_='s2')
                            if time_elem:
                                time_text = time_elem.get_text(strip=True)
                                if time_text:
                                    date_text = self._parse_relative_time(time_text)
                        
                        # 检查是否在时间范围内
                        if date_text and self._is_in_range(date_text):
                            page_valid_count += 1
                            # 搜狗返回的是相对链接，需要拼接完整URL
                            if article_url.startswith('/'):
                                article_url = f"https://weixin.sogou.com{article_url}"
                            
                            # 获取真实微信链接
                            real_url = self._get_real_wechat_url(article_url)
                            if real_url:
                                items.append({
                                    "title": title,
                                    "date": date_text,
                                    "url": real_url,
                                    "source": source_label,
                                })
                                logger.info(f"  ✓ {title[:40]}... ({date_text})")
                        
                    except Exception as e:
                        logger.warning(f"  解析文章失败: {e}")
                        continue
                
                logger.info(f"  第 {page} 页符合时间范围: {page_valid_count} 篇")
                
                # 添加延迟，避免请求过快
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"搜狗微信搜索请求失败: {keyword}, 页码: {page}, 错误: {e}")
                break
        
        return items
    
    def _parse_relative_time(self, time_text):
        """解析相对时间"""
        now = datetime.now()
        
        if '分钟前' in time_text:
            return now.strftime("%Y-%m-%d")
        elif '小时前' in time_text:
            return now.strftime("%Y-%m-%d")
        elif '昨天' in time_text:
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")
        elif '前天' in time_text:
            return (now - timedelta(days=2)).strftime("%Y-%m-%d")
        elif '天前' in time_text:
            match = re.search(r'(\d+)天前', time_text)
            if match:
                days = int(match.group(1))
                return (now - timedelta(days=days)).strftime("%Y-%m-%d")
        
        return ""
    
    def _get_real_wechat_url(self, sogou_url):
        """获取搜狗跳转后的真实微信文章链接"""
        try:
            # 搜狗的链接是跳转链接，需要跟随重定向
            resp = self.session.head(sogou_url, allow_redirects=True, timeout=10)
            return resp.url
        except:
            # 如果获取失败，返回原始链接
            return sogou_url

    # ==================== 获取摘要 ====================
    def _get_summary(self, url):
        """从详情页获取摘要信息"""
        html = self._fetch(url)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        # 尝试获取 meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()[:100]
        # 尝试获取 title
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)[:100]
        return ""

    # ==================== 主爬取流程 ====================
    def crawl_all(self):
        """爬取所有网站"""
        logger.info(f"开始爬取，时间范围: 最近 {self.days} 天（从 {self.cutoff_date.strftime('%Y-%m-%d')} 至今）")
        start_time = time.time()

        # 官方五个法规来源，以及新增的两个法律专业门户。
        self.crawl_flk_npc()
        time.sleep(1)
        self.crawl_gov_cn()
        time.sleep(1)
        self.crawl_npc_gov()
        time.sleep(1)
        self.crawl_moj_gov()
        time.sleep(1)
        self.crawl_court_gov()
        time.sleep(1)
        self.crawl_court_case_77()
        time.sleep(1)
        self.crawl_legal_portal("wkinfo")
        time.sleep(1)
        self.crawl_legal_portal("pkulaw")
        time.sleep(1)

        # 按日期降序排序
        self.results.sort(key=lambda x: x.get("date", ""), reverse=True)

        elapsed = time.time() - start_time
        logger.info(f"爬取完成，共获取 {len(self.results)} 条法律信息，耗时 {elapsed:.1f} 秒")

    # ==================== 输出结果 ====================
    def save_core_outputs(self, law_output=None, case_output=None):
        """按记录分类写入法律条文和指导案例文件。"""
        law_output = law_output or LAW_OUTPUT_FILE
        case_output = case_output or CASE_OUTPUT_FILE
        case_keys = {(item.get("title"), item.get("url")) for item in self.case_results}
        law_items = [
            item
            for item in self.results
            if (item.get("title"), item.get("url")) not in case_keys
        ]
        self._write_items_file(law_output, law_items, "法律法规信息")
        self._write_items_file(case_output, self.case_results, "最高人民法院案例信息")
        logger.info(
            f"核心文件已更新: {law_output} {len(law_items)} 条，{case_output} {len(self.case_results)} 条"
        )

    def save_items_file(self, output_file, items):
        """将爬取记录按固定四字段格式写入文件。"""
        self._write_items_file(output_file, items, "")

    def _write_items_file_legacy(self, output_file, items, heading):
        """写入统一的标题、来源、日期、链接格式。"""
        with open(output_file, "w", encoding="utf-8") as f:
            if heading:
                f.write(f"{heading}\n")
                f.write(f"共 {len(items)} 条\n")
                f.write("=" * 60 + "\n\n")
            for item in sorted(items, key=lambda value: value.get("date", ""), reverse=True):
                title = " ".join(item.get("title", "").split())
                f.write(f"标题：{title}\n")
                f.write(f"来源：{item.get('source', '')}\n")
                f.write(f"日期：{item.get('date', '')}\n")
                f.write(f"链接：{item.get('url', '')}\n\n")

    def _write_items_file(self, output_file, items, heading):
        """Write records in the required UTF-8 four-field format."""
        with open(output_file, "w", encoding="utf-8") as f:
            for item in sorted(items, key=lambda value: value.get("date", ""), reverse=True):
                title = " ".join(str(item.get("title", "")).split())
                f.write(f"\u6807\u9898\uff1a{title}\n")
                f.write(f"\u6765\u6e90\uff1a{item.get('source', '')}\n")
                f.write(f"\u65e5\u671f\uff1a{item.get('date', '')}\n")
                f.write(f"\u94fe\u63a5\uff1a{item.get('url', '')}\n\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="法律信息爬虫")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"时间范围（天），默认 {DEFAULT_DAYS}")
    args = parser.parse_args()

    crawler = LawCrawler(days=args.days)
    crawler.crawl_all()
    crawler.save_core_outputs()


if __name__ == "__main__":
    main()
