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
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.ssl_ import create_urllib3_context
except ImportError:
    create_urllib3_context = None

from config import HEADERS, TIMEOUT, DEFAULT_DAYS, OUTPUT_FILE, SITES, WECHAT_ACCOUNTS, SOGOU_WEIXIN

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
        return dt >= self.cutoff_date



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
    def crawl_court_gov(self):
        """爬取最高人民法院 - 只爬取司法解释、典型案例等法律内容"""
        logger.info("开始爬取: 最高人民法院")
        site = SITES["court_gov"]
        
        # 只爬取法律相关栏目
        urls_to_try = [
            f"{site['base_url']}/zixun/gengduo/23.html",  # 司法解释
            f"{site['base_url']}/zixun/gengduo/24.html",  # 典型案例
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
        """通过搜狗微信搜索获取文章"""
        items = []
        
        # 构建搜索URL
        base_url = SOGOU_WEIXIN["base_url"]
        search_type = SOGOU_WEIXIN["type"]
        search_url = f"{base_url}?type={search_type}&query={keyword}"
        
        try:
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': 'https://weixin.sogou.com/',
            }
            
            resp = self.session.get(search_url, headers=headers, timeout=TIMEOUT)
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                logger.warning(f"搜狗微信搜索失败: {keyword}, 状态码: {resp.status_code}")
                return items
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 查找文章列表 - 使用正确的选择器
            txt_boxes = soup.select('div.txt-box')
            logger.info(f"  找到 {len(txt_boxes)} 个文章容器")
            
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
                        # 从 script 标签中提取时间戳
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
                    else:
                        logger.debug(f"  跳过文章（日期不符合）: {title[:30]}, 日期: {date_text}")
                
                except Exception as e:
                    logger.warning(f"  解析文章失败: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"搜狗微信搜索请求失败: {keyword}, 错误: {e}")
        
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

        # 原有网站
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
        
        # 新增公众号和网站
        self.crawl_spp_gov()
        time.sleep(1)
        self.crawl_wenshu_court()
        time.sleep(1)
        self.crawl_court_research()
        time.sleep(1)
        self.crawl_tianping()
        time.sleep(1)
        self.crawl_china_pufa()
        time.sleep(1)

        # 微信公众号
        self.crawl_wechat_accounts()

        # 按日期降序排序
        self.results.sort(key=lambda x: x.get("date", ""), reverse=True)

        elapsed = time.time() - start_time
        logger.info(f"爬取完成，共获取 {len(self.results)} 条法律信息，耗时 {elapsed:.1f} 秒")

    # ==================== 输出结果 ====================
    def save_results(self, output_file=None, fetch_summary=False):
        """保存结果到文件"""
        output_file = output_file or OUTPUT_FILE
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"法律信息爬取结果\n")
            f.write(f"时间范围: 最近 {self.days} 天（从 {self.cutoff_date.strftime('%Y-%m-%d')} 至 {datetime.now().strftime('%Y-%m-%d')}）\n")
            f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"共 {len(self.results)} 条\n")
            f.write("=" * 60 + "\n\n")

            for item in self.results:
                # 清理标题中的换行符和多余空白
                title = ' '.join(item['title'].split())
                f.write(f"{title}\n")
                f.write(f"来源：{item['source']}｜日期：{item['date']}\n")
                f.write(f"链接：{item['url']}\n")
                if fetch_summary:
                    summary = self._get_summary(item["url"])
                    if summary:
                        f.write(f"摘要：{summary}\n")
                f.write("\n")

        logger.info(f"结果已保存到: {output_file}")
        return output_file

    def print_results(self):
        """打印结果到控制台"""
        print(f"\n{'='*60}")
        print(f"法律信息爬取结果（最近 {self.days} 天）")
        print(f"共 {len(self.results)} 条")
        print(f"{'='*60}\n")

        for item in self.results:
            print(item['title'])
            print(f"来源：{item['source']}｜日期：{item['date']}")
            print(f"链接：{item['url']}")
            print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="法律信息爬虫")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"时间范围（天），默认 {DEFAULT_DAYS}")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    args = parser.parse_args()

    crawler = LawCrawler(days=args.days)
    crawler.crawl_all()
    crawler.print_results()
    crawler.save_results(args.output)


if __name__ == "__main__":
    main()
