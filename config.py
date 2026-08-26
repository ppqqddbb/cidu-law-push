# -*- coding: utf-8 -*-
"""爬虫配置文件"""

import os
from datetime import datetime

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# 请求超时（秒）
TIMEOUT = 15

# 默认时间范围（天）
DEFAULT_DAYS = 7

# 输出文件路径
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
# result.txt stores the complete crawl before Dify filtering.
RESULT_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "result.txt")
LAW_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "law.txt")
CASE_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "case.txt")

# Dify agent connection settings. Environment variables can override these
# values when run_filter.py is started.
DIFY_API_URL = "http://ciduai.daneng.cc/v1"
DIFY_API_KEY = "app-9vafjQOyvM8j25Y4u43P8lLx"

# 各网站配置
SITES = {
    "flk_npc": {
        "name": "国家法律法规数据库",
        "base_url": "https://flk.npc.gov.cn",
        "source_label": "国家法律法规数据库",
    },
    "gov_cn": {
        "name": "中国政府网·政策文件库",
        "base_url": "https://www.gov.cn/zhengce",
        "source_label": "中国政府网·政策文件库",
    },
    "npc_gov": {
        "name": "中国人大网",
        "base_url": "https://www.npc.gov.cn",
        "source_label": "中国人大网",
    },
    "moj_gov": {
        "name": "司法部 / 中国政府法制信息网",
        "base_url": "https://www.moj.gov.cn",
        "source_label": "司法部 / 中国政府法制信息网",
    },
    "court_gov": {
        "name": "最高人民法院",
        "base_url": "https://www.court.gov.cn",
        "source_label": "最高人民法院",
    },
    "wkinfo": {
        "name": "威科先行",
        "base_url": "https://law.wkinfo.com.cn",
        "source_label": "威科先行",
        "entry_urls": ["https://law.wkinfo.com.cn/"],
        "allowed_hosts": ["law.wkinfo.com.cn", "wkinfo.com.cn"],
    },
    "pkulaw": {
        "name": "北大法宝",
        "base_url": "https://www.pkulaw.com",
        "source_label": "北大法宝",
        "entry_urls": ["https://www.pkulaw.com/"],
        "allowed_hosts": ["www.pkulaw.com", "pkulaw.com"],
    },
}

# 最高人民法院案例来源。修改此处即可切换案例栏目，无需改爬虫代码。
COURT_CASE_SOURCE = {
    "name": "最高人民法院案例",
    "list_url": "https://www.court.gov.cn/shenpan/gengduo/77.html",
    "breadcrumb": ["首页", "审判业务", "指导案例"],
    "source_label": "最高人民法院",
}
