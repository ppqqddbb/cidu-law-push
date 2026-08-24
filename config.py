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
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "result.txt")
LAW_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "law.txt")
CASE_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "case.txt")

# Dify 大模型配置
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
        "name": "司法部",
        "base_url": "https://www.moj.gov.cn",
        "source_label": "司法部",
    },
    "court_gov": {
        "name": "最高人民法院",
        "base_url": "https://www.court.gov.cn",
        "source_label": "最高人民法院",
    },
    "spp_gov": {
        "name": "最高人民检察院",
        "base_url": "https://www.spp.gov.cn",
        "source_label": "最高人民检察院",
    },
    "wenshu_court": {
        "name": "中国裁判文书网",
        "base_url": "https://wenshu.court.gov.cn",
        "source_label": "中国裁判文书网",
    },
    "court_research": {
        "name": "最高人民法院司法案例研究院",
        "base_url": "https://www.court.gov.cn",
        "source_label": "最高人民法院司法案例研究院",
    },
    "tianping": {
        "name": "天平阳光",
        "base_url": "https://www.court.gov.cn/tianping/",
        "source_label": "天平阳光",
    },
    "china_pufa": {
        "name": "中国普法",
        "base_url": "https://www.moj.gov.cn",
        "source_label": "中国普法",
    },
}

# 搜狗微信搜索配置
SOGOU_WEIXIN = {
    "base_url": "https://weixin.sogou.com/weixin",
    "type": 2,  # 2=搜文章, 1=搜公众号
    "source_label": "微信公众号",
}

# 山东高法官网指导案例列表
SDCOURT_CASE_LIST_URL = "https://www.sdcourt.gov.cn/nwglpt/7278484/index.html"

# Official court websites used by the case crawler.  Seed URLs are deliberately
# kept public and configurable because court CMS paths can change independently.
COURT_SITES = {
    "sdcourt": {
        "name": "山东高法",
        "source_label": "山东高法官网",
        "base_url": "https://www.sdcourt.gov.cn/",
        "seed_urls": [SDCOURT_CASE_LIST_URL, "https://www.sdcourt.gov.cn/"],
        "keywords": ["案例", "指导", "典型", "裁判", "判决", "审判", "执行"],
        "case_terms": ["案例", "指导", "典型", "裁判", "判决", "减刑", "执行案件"],
    },
    "shanghai_first": {
        "name": "上海一中法院",
        "source_label": "上海一中法院官网",
        "base_url": "https://www.a-court.gov.cn/",
        "seed_urls": ["https://www.a-court.gov.cn/"],
        "keywords": ["案例", "典型", "裁判", "判决", "审判", "执行"],
        "case_terms": ["案例", "指导", "典型", "裁判", "判决", "减刑", "执行案件"],
    },
    "shanghai_second": {
        "name": "上海二中法院",
        "source_label": "上海二中法院官网",
        "base_url": "https://www.shezfy.gov.cn/",
        "seed_urls": ["https://www.shezfy.gov.cn/"],
        "keywords": ["案例", "典型", "裁判", "判决", "审判", "执行"],
        "case_terms": ["案例", "指导", "典型", "裁判", "判决", "减刑", "执行案件"],
    },
    "suzhou": {
        "name": "苏州中级法院",
        "source_label": "苏州中级法院官网",
        "base_url": "https://www.szfy.gov.cn/",
        "seed_urls": [
            "https://www.szfy.gov.cn/",
            "http://www.szfy.gov.cn/",
            "https://www.suzhoucourt.gov.cn/",
            "http://www.suzhoucourt.gov.cn/",
            "https://www.szzy.gov.cn/",
        ],
        "domains": ["www.szzy.gov.cn", "www.suzhoucourt.gov.cn"],
        "keywords": ["案例", "典型", "裁判", "判决", "审判", "执行"],
        "case_terms": ["案例", "指导", "典型", "裁判", "判决", "减刑", "执行案件"],
    },
    "shenzhen": {
        "name": "深圳中级人民法院",
        "source_label": "深圳中级人民法院官网",
        "base_url": "https://www.szcourt.gov.cn/",
        "seed_urls": ["https://www.szcourt.gov.cn/"],
        "keywords": ["案例", "典型", "裁判", "判决", "审判", "执行"],
        "case_terms": ["案例", "指导", "典型", "裁判", "判决", "减刑", "执行案件"],
    },
}

# 目标微信公众号列表（用于 Playwright 搜狗搜索爬取）
WECHAT_ARTICLES = [
    {"account": "山东高法", "province": "山东", "category": "案例检索"},
]

# 微信公众号标题输出文件
WECHAT_TITLE_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "wechat_titles.txt")

# 微信公众号搜索关键词配置
WECHAT_ACCOUNTS = {
    "山东高法": {
        "keywords": ["山东高法", "山东省高级人民法院", "山东高院"],
        "source_label": "山东高法",
    },
}
