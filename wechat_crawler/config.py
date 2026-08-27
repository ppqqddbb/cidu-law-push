# -*- coding: utf-8 -*-
"""微信公众号采集器配置"""

import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

# 公众号配置
ACCOUNTS_YAML = BASE_DIR / "config" / "wechat_accounts.yaml"

# 数据目录
DATA_DIR = BASE_DIR / "data"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"
DB_PATH = DATA_DIR / "wechat_urls.sqlite"

# 输出
OUTPUT_CSV = BASE_DIR / "wechat_titles_playwright.csv"

# 搜狗微信搜索
SOGOU_WEIXIN_URL = "https://weixin.sogou.com/weixin"

# 日期正则
import re
DATE_RE = re.compile(
    r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
    r"|(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
)

# 微信文章 URL 正则
WECHAT_ARTICLE_RE = re.compile(r"mp\.weixin\.qq\.com/s[?/]")


def load_accounts():
    """加载公众号配置"""
    if not ACCOUNTS_YAML.exists():
        return []
    with open(ACCOUNTS_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("accounts", [])


def ensure_dirs():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
