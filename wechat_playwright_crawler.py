#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信公众号文章采集器
技术栈: Playwright + Chromium + 微信登录态

原理:
- 公众号主页(profile_ext?action=home)按时间倒序排列文章
- 但需要微信登录态才能访问
- 本采集器通过 Playwright 持久化浏览器会话，首次扫码登录后复用会话

用法:
    # 首次运行（需要扫码登录）
    python wechat_playwright_crawler.py --start 2026-08-17 --end 2026-08-24
    
    # 后续运行（复用登录态，可无界面）
    python wechat_playwright_crawler.py --start 2026-08-17 --end 2026-08-24 --headless
"""

import argparse
import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from config import WECHAT_ARTICLES


# 微信公众号主页 URL 模板
PROFILE_URL = "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz={biz}&scene=124#wechat_redirect"

# 微信登录页
WECHAT_LOGIN_URL = "https://mp.weixin.qq.com/"

# 日期正则
DATE_RE = re.compile(
    r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
    r"|(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
)


def parse_args():
    parser = argparse.ArgumentParser(description="微信公众号文章采集器 (Playwright + Chromium)")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD（包含）")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD（包含）")
    parser.add_argument("--out", default="wechat_titles_playwright.csv", help="输出 CSV 文件路径")
    parser.add_argument("--profile", default="wechat-playwright-profile", help="浏览器会话保存目录")
    parser.add_argument("--max-pages", type=int, default=10, help="每个公众号最多翻页数")
    parser.add_argument("--browser", choices=("chrome", "chromium"), default="chrome", help="浏览器类型")
    parser.add_argument("--headless", action="store_true", help="无界面运行（首次不要使用）")
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


def extract_biz_from_url(url):
    """从 URL 中提取 __biz 参数"""
    query = parse_qs(urlparse(url).query)
    biz_list = query.get("__biz")
    if biz_list:
        return biz_list[0].replace("\\x3d", "=")
    return ""


def find_biz_in_html(html):
    """从页面 HTML 中提取 __biz"""
    patterns = [
        r"[?&]__biz=([^&\"'\\]+)",
        r"(?:var|window)\.biz\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:__biz|biz)\s*[:=]\s*['\"]([^'\"]+)['\"]",
        r'var\s+biz\s*=\s*["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "")
        if match:
            val = match.group(1).replace("\\x3d", "=")
            if val and not val.startswith("$"):
                return val
    return ""


def get_biz_from_page(page):
    """从页面 JS 上下文中获取 __biz"""
    try:
        js_biz = page.evaluate("() => window.biz || ''")
        if js_biz and not js_biz.startswith("$"):
            return js_biz
    except Exception:
        pass
    return ""


def wait_for_login(page, timeout_sec=180):
    """等待用户完成微信登录"""
    print("    等待微信登录...请在弹出的浏览器中扫码或确认登录")
    print("    (超时时间: {} 秒)".format(timeout_sec))
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        url = page.url
        title = page.title()
        # 检查是否已登录（进入公众号平台首页）
        if 'mp.weixin.qq.com' in url and ('cgi-bin' in url or 'home' in url.lower()):
            if '登录' not in title and 'login' not in title.lower():
                print("    登录成功!")
                return True
        time.sleep(2)
    print("    登录超时!")
    return False


def check_login_status(page):
    """检查当前是否已登录"""
    try:
        page.goto(WECHAT_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        url = page.url
        title = page.title()
        # 如果登录后会跳转到首页
        if 'cgi-bin/home' in url or 'cgi-bin/frame' in url:
            return True
        # 如果还在登录页
        if 'login' in url.lower() or '登录' in title:
            return False
        return True
    except Exception:
        return False


def extract_profile_entries(page, account, start, end):
    """从公众号主页提取文章列表"""
    items = []

    # 滚动加载更多内容
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

    # 提取所有微信文章链接
    links_data = page.evaluate("""() => {
        const results = [];
        const allLinks = document.querySelectorAll('a[href]');
        allLinks.forEach(a => {
            const href = a.href || '';
            if (href.includes('mp.weixin.qq.com/s') || href.includes('/s?')) {
                const box = a.closest('.weui_media_box, .weui_media_box_appmsg, .appmsg_item, .list_item, li, .rich_media_area_primary_inner') || a.parentElement;
                results.push({
                    href: href,
                    text: (box?.innerText || a.innerText || '').trim().substring(0, 300),
                    aText: (a.innerText || '').trim().substring(0, 300),
                });
            }
        });
        return results;
    }""")

    seen_urls = set()
    for link in links_data:
        href = link["href"]
        text = link["text"] or link["aText"]

        if not text or href in seen_urls:
            continue
        seen_urls.add(href)

        # 从文本中提取日期
        date_text = ""
        match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
        if match:
            date_text = "{}-{:02d}-{:02d}".format(match.group(1), int(match.group(2)), int(match.group(3)))

        # 检查日期范围
        item_date = parse_date_text(date_text)
        if not item_date or item_date < start or item_date > end:
            continue

        # 提取标题（取第一行非空文本）
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        title = lines[0] if lines else text[:100]

        items.append({
            "title": re.sub(r"\s+", " ", title).strip(),
            "source": account,
            "date": date_text,
            "summary": "",
            "url": href,
        })

    return items


def crawl_account_homepage(page, account, biz, start, end, max_pages):
    """通过公众号主页爬取文章"""
    profile_url = PROFILE_URL.format(biz=biz)
    print("  打开主页: ...{}".format(biz[-10:]))

    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # 检查是否需要登录
        page_text = page.inner_text("body")
        if "请在微信客户端打开" in page_text or "登录" in page.title():
            print("    需要微信登录态，跳过")
            return []

        all_items = []
        for i in range(max_pages):
            items = extract_profile_entries(page, account, start, end)
            print("    第 {} 次提取: {} 条".format(i + 1, len(items)))
            all_items.extend(items)

            # 尝试点击"加载更多"或"查看更多"
            clicked = False
            for selector in ["text=更多", "text=查看更多", "text=加载更多", "#js_more"]:
                try:
                    btn = page.locator(selector).last
                    if btn.count() and btn.is_visible(timeout=500):
                        btn.click(timeout=1000)
                        page.wait_for_timeout(2000)
                        clicked = True
                        break
                except Exception:
                    pass

            if not clicked:
                break

        return all_items

    except Exception as e:
        print("    错误: {}".format(e))
        return []


def get_biz_from_sogou(page, context, account):
    """通过搜狗搜索获取公众号的 __biz"""
    sogou_search = "https://weixin.sogou.com/weixin?type=2&query={}".format(quote(account))
    print("  通过搜狗搜索获取 __biz...")

    try:
        page.goto(sogou_search, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        # 从搜索结果第一个链接中提取 biz
        first_link = page.query_selector('div.txt-box a')
        if first_link:
            href = first_link.get_attribute('href') or ''
            print("    搜狗链接: {}...".format(href[:100]))
            if href.startswith('/'):
                href = "https://weixin.sogou.com{}".format(href)
            # 跟随重定向获取真实微信链接
            resp = context.request.get(href, max_redirects=5)
            final_url = resp.url
            print("    真实URL: {}...".format(final_url[:150]))
            biz = extract_biz_from_url(final_url)
            if not biz:
                # 从文章页面 HTML 中提取 biz
                article_html = resp.text()
                biz = find_biz_in_html(article_html)
            if biz:
                print("    获取到 __biz: {}...".format(biz[:20]))
                return biz
            else:
                print("    未能从文章链接中提取 __biz")
    except Exception as e:
        print("    搜狗搜索失败: {}".format(e))

    return ""


def main():
    args = parse_args()
    end = parse_day(args.end, date.today())
    start = parse_day(args.start, end - timedelta(days=7))
    if start > end:
        raise SystemExit("--start 不能晚于 --end")

    print("微信公众号文章采集器 (Playwright + Chromium)")
    print("时间范围: {} 至 {}".format(start, end))
    print("目标公众号: {} 个".format(len(WECHAT_ARTICLES)))
    print("=" * 60)

    output_path = Path(args.out)
    all_rows = []

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=args.profile,
            headless=args.headless,
            channel="chrome" if args.browser == "chrome" else None,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
        )

        try:
            # 检查登录状态
            login_page = context.new_page()
            is_logged_in = check_login_status(login_page)
            login_page.close()

            if not is_logged_in:
                print("\n需要微信登录!")
                print("请在弹出的浏览器中完成扫码登录...")
                login_page = context.new_page()
                login_page.goto(WECHAT_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                if not wait_for_login(login_page, timeout_sec=180):
                    print("登录失败，退出")
                    return
                login_page.close()
                print("登录成功，会话已保存\n")
            else:
                print("已检测到登录态\n")

            for article in WECHAT_ARTICLES:
                account = article["account"]
                print("-" * 60)
                print("公众号: {}".format(account))

                page = context.new_page()

                # 步骤1: 通过搜狗搜索获取 __biz
                biz = get_biz_from_sogou(page, context, account)

                # 步骤2: 如果没获取到 biz，尝试从页面 JS 获取
                if not biz:
                    print("  尝试从页面上下文获取 __biz...")
                    biz = get_biz_from_page(page)
                    if biz:
                        print("    获取到 __biz: {}...".format(biz[:20]))

                # 步骤3: 有 biz 则访问公众号主页
                if biz:
                    print("  访问公众号主页...")
                    items = crawl_account_homepage(page, account, biz, start, end, args.max_pages)
                    print("  共 {} 条".format(len(items)))
                    all_rows.extend(items)
                else:
                    print("  [X] 无法获取 {} 的 __biz，跳过".format(account))

                page.close()
                time.sleep(2)

        finally:
            context.close()

    # 去重
    unique = {}
    for row in all_rows:
        key = (row["source"], row["title"])
        if key not in unique:
            unique[key] = row
    rows = sorted(unique.values(), key=lambda item: (item["date"] or "", item["source"]), reverse=True)

    # 输出 CSV
    with output_path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(("标题", "来源", "时间", "摘要", "链接"))
        for row in rows:
            writer.writerow((row["title"], row["source"], row["date"], row["summary"], row["url"]))

    print("\n" + "=" * 60)
    print("采集完成! 共 {} 条文章".format(len(rows)))
    print("已保存到: {}".format(output_path))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n已取消")
