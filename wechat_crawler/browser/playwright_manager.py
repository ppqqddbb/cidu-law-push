# -*- coding: utf-8 -*-
"""Playwright 浏览器管理器 - 持久化 Chromium 会话"""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class PlaywrightManager:
    """管理 Playwright 持久化浏览器上下文"""

    def __init__(self, profile_dir: str, headless: bool = False):
        self.profile_dir = profile_dir
        self.headless = headless
        self._playwright = None
        self._context = None

    def start(self):
        """启动浏览器"""
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            channel="chrome",
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
        )
        return self._context

    def stop(self):
        """关闭浏览器"""
        if self._context:
            self._context.close()
            self._context = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def new_page(self):
        """创建新页面"""
        if not self._context:
            raise RuntimeError("浏览器未启动，请先调用 start()")
        return self._context.new_page()

    @property
    def context(self):
        """返回当前浏览器上下文，供浏览器型发现器复用会话。"""
        return self._context

    def resolve_url(self, url: str, max_redirects: int = 5) -> str:
        """跟踪 URL 重定向，返回最终 URL"""
        try:
            resp = self._context.request.get(url, max_redirects=max_redirects)
            return resp.url
        except Exception:
            return url

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
