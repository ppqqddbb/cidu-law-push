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

# 微信公众号搜索关键词配置
WECHAT_ACCOUNTS = {
    "山东高法": {"keywords": ["山东高法"], "source_label": "山东高法"},
    "上海法院": {"keywords": ["上海法院", "上海高院"], "source_label": "上海法院"},
    "京法网事": {"keywords": ["京法网事", "北京高院"], "source_label": "京法网事"},
    "江苏高院": {"keywords": ["江苏高院"], "source_label": "江苏高院"},
    "浙江法院": {"keywords": ["浙江法院"], "source_label": "浙江法院"},
    "广东法院": {"keywords": ["广东法院"], "source_label": "广东法院"},
    "豫法阳光": {"keywords": ["豫法阳光", "河南高院"], "source_label": "豫法阳光"},
    "湖南高法": {"keywords": ["湖南高法"], "source_label": "湖南高法"},
    "鄂法在线": {"keywords": ["鄂法在线", "湖北高院"], "source_label": "鄂法在线"},
    "四川高院": {"keywords": ["四川高院"], "source_label": "四川高院"},
    "福建高院": {"keywords": ["福建高院"], "source_label": "福建高院"},
    "安徽高院": {"keywords": ["安徽高院"], "source_label": "安徽高院"},
    "陕西高院": {"keywords": ["陕西高院"], "source_label": "陕西高院"},
    "重庆高院": {"keywords": ["重庆高院"], "source_label": "重庆高院"},
    "天津高院": {"keywords": ["天津高院"], "source_label": "天津高院"},
    "河北高院": {"keywords": ["河北高院"], "source_label": "河北高院"},
    "上海一中院": {"keywords": ["上海一中院", "上海一中法院"], "source_label": "上海一中院"},
    "上海二中院": {"keywords": ["上海二中院", "上海二中法院"], "source_label": "上海二中院"},
    "苏州中院": {"keywords": ["苏州中院", "苏州中级法院"], "source_label": "苏州中院"},
    "深圳中院": {"keywords": ["深圳中院", "深圳中级人民法院"], "source_label": "深圳中院"},
    "广州中院": {"keywords": ["广州中院", "广州中级人民法院"], "source_label": "广州中院"},
    "北京一中院": {"keywords": ["北京一中院", "北京一中法院"], "source_label": "北京一中院"},
    "杭州中院": {"keywords": ["杭州中院", "杭州中级法院"], "source_label": "杭州中院"},
    "南京中院": {"keywords": ["南京中院", "南京中级法院"], "source_label": "南京中院"},
    "成都中院": {"keywords": ["成都中院", "成都中级法院"], "source_label": "成都中院"},
    "重庆五中院": {"keywords": ["重庆五中院"], "source_label": "重庆五中院"},
    "武汉中院": {"keywords": ["武汉中院", "武汉中级法院"], "source_label": "武汉中院"},
    "西安中院": {"keywords": ["西安中院", "西安中级法院"], "source_label": "西安中院"},
    "青岛中院": {"keywords": ["青岛中院", "青岛中级法院"], "source_label": "青岛中院"},
    "宁波中院": {"keywords": ["宁波中院", "宁波中级法院"], "source_label": "宁波中院"},
    "最高人民法院": {"keywords": ["最高人民法院"], "source_label": "最高人民法院"},
    "最高人民法院司法案例研究院": {"keywords": ["最高人民法院司法案例研究院"], "source_label": "最高人民法院司法案例研究院"},
    "天平阳光": {"keywords": ["天平阳光"], "source_label": "天平阳光"},
    "中国普法": {"keywords": ["中国普法"], "source_label": "中国普法"},
    "最高人民检察院": {"keywords": ["最高人民检察院"], "source_label": "最高人民检察院"},
}
