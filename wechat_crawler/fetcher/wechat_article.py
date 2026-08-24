# -*- coding: utf-8 -*-
"""微信文章采集器 - 通过 Playwright 访问文章页面"""

import re
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class WechatArticleFetcher:
    """通过 Playwright 访问微信文章页面，提取正文内容"""

    def __init__(self, browser_manager):
        self.browser = browser_manager

    def fetch(self, url: str) -> Optional[dict]:
        """
        访问微信文章页面，提取文章信息。

        Returns:
            {
                "url": str,
                "title": str,
                "account": str,         # 公众号名称
                "publish_time": str,    # 发布时间
                "author": str,
                "content": str,         # 正文文本
                "images": list,
            }
            或 None（访问失败）
        """
        page = None
        try:
            page = self.browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # 搜狗链接可能需要在浏览器环境中才能完成跳转。
            final_url = page.url
            if "mp.weixin.qq.com/s" not in final_url:
                article_link = page.query_selector('a[href*="mp.weixin.qq.com/s"]')
                if article_link:
                    target_url = article_link.get_attribute("href") or ""
                    if target_url:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(1500)
                        final_url = page.url

            # 检查是否被拦截
            page_text = page.inner_text("body")
            if "环境异常" in page_text or "网络环境存在异常" in page_text:
                print("    文章页面被拦截: {}".format(url[:80]))
                return None

            # 提取标题
            title = ""
            title_elem = page.query_selector("#activity-name")
            if title_elem:
                title = title_elem.inner_text().strip()

            # 提取公众号名称
            account = ""
            account_elem = page.query_selector("#js_name")
            if account_elem:
                account = account_elem.inner_text().strip()
            if not account:
                profile_link = page.query_selector("#js_profile_qrcode a, .profile_nickname")
                if profile_link:
                    account = profile_link.inner_text().strip()

            # 提取发布时间
            publish_time = ""
            publish_elem = page.query_selector("#publish_time")
            if publish_elem:
                publish_time = publish_elem.inner_text().strip()
            if not publish_time:
                # 尝试从页面文本中提取
                match = re.search(
                    r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})",
                    page_text[:500]
                )
                if match:
                    publish_time = "{}-{:02d}-{:02d}".format(
                        match.group(1), int(match.group(2)), int(match.group(3))
                    )

            # 提取作者
            author = ""
            author_elem = page.query_selector("#js_author")
            if author_elem:
                author = author_elem.inner_text().strip()

            # 提取正文
            content = ""
            content_elem = page.query_selector("#js_content")
            if content_elem:
                content = content_elem.inner_text().strip()

            # 提取图片
            images = []
            img_elems = page.query_selector_all("#js_content img")
            for img in img_elems:
                src = img.get_attribute("data-src") or img.get_attribute("src") or ""
                if src and src.startswith("http"):
                    images.append(src)

            if not title:
                return None

            return {
                "url": final_url if "mp.weixin.qq.com/s" in final_url else url,
                "title": title,
                "account": account,
                "publish_time": publish_time,
                "author": author,
                "content": content,
                "images": images,
            }

        except PlaywrightTimeoutError:
            print("    文章页面加载超时: {}".format(url[:80]))
            return None
        except Exception as e:
            print("    文章页面访问失败: {} - {}".format(url[:80], e))
            return None
        finally:
            if page:
                page.close()
