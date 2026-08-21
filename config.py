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
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "law_output.txt")

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

# 微信公众号链接配置
WECHAT_ACCOUNTS = {
    "山东高法": [
        "https://mp.weixin.qq.com/s/4Hd843YWk18JpAV6_q_aeg",
    ],
    "上海法院": [
        "https://mp.weixin.qq.com/s/wwxdgzJyFRjbU5Y_R2Zzyg",
    ],
    "京法网事": [
        "https://mp.weixin.qq.com/s/QR574A_UKx7hFrgD3CkQDw",
    ],
    "江苏高院": [
        "https://mp.weixin.qq.com/s/6-hV5_zksOtotwv35gAhZA",
    ],
    "浙江法院": [
        "https://mp.weixin.qq.com/s/w0AhA-hElkTNGIL0dK9pFQ",
    ],
    "广东法院": [
        "https://mp.weixin.qq.com/s/uwzcINNZbJ2oMWDarPCD1A",
    ],
    "豫法阳光": [
        "http://mp.weixin.qq.com/s?__biz=MzA5NzAwNDU0MQ==&mid=2658541737&idx=1&sn=4bfbb2db85c766b21cbef88a4944fc60",
    ],
    "湖南高法": [
        "https://mp.weixin.qq.com/s/mzTGLtLh9IOT-HxQ3oKhVg",
    ],
    "鄂法在线": [
        "https://mp.weixin.qq.com/s/tZ7WHChbEngkEZ5uO1dCGg",
    ],
    "四川高院": [
        "https://mp.weixin.qq.com/s/0IguG7iPpT7XYql9zCgmdQ",
    ],
    "福建高院": [
        "https://mp.weixin.qq.com/s/PhuwmfSLkR4980Ehdx7ZdQ",
    ],
    "安徽高院": [
        "https://mp.weixin.qq.com/s/PGrTDLHnQv0M1oL0tjXvyw",
    ],
    "陕西高院": [
        "https://mp.weixin.qq.com/s/mnLWfncqzT0lgcor51wWWw",
    ],
    "重庆高院": [
        "https://mp.weixin.qq.com/s/xV7X27sQUyBhOEWa3WySoQ",
    ],
    "天津高院": [
        "https://mp.weixin.qq.com/s/-9A-eWxIrbjX2FRC6O3JdA",
    ],
    "河北高院": [
        "https://mp.weixin.qq.com/s/xY9Xj8Woyzyihc9yvXdj1A",
    ],
    "上海一中院": [
        "http://mp.weixin.qq.com/s?__biz=MjM5MjkwMDkxMA==&mid=2649585987&idx=1&sn=fbcc6d640343e7288ad56bf07ab8e026",
    ],
    "上海二中院": [
        "http://mp.weixin.qq.com/s?__biz=MzA4MzY3NjMxNw==&mid=2656555839&idx=1&sn=8bcb8679fb1a64c3436d55a66e425a56",
    ],
    "苏州中院": [
        "https://mp.weixin.qq.com/s/gwfYrmWAtI8up4Kt0cElgw",
    ],
    "深圳中院": [
        "http://mp.weixin.qq.com/s?__biz=MzA3ODA0OTEyMg==&mid=2653977723&idx=1&sn=eab47c61d32438d108d700bf43514a40",
    ],
    "广州中院": [
        "https://mp.weixin.qq.com/s/hzZC7oVfem06_hWJUezFDQ",
    ],
    "北京一中院": [
        "http://mp.weixin.qq.com/s?__biz=MzI5NTkxMDU2NQ==&mid=2247630946&idx=1&sn=17705c374ff0c0d7dea15fef1300edd0",
    ],
    "杭州中院": [
        "https://mp.weixin.qq.com/s/x-GfvPV9nv9beq_Qa0EBtg",
    ],
    "南京中院": [
        "https://mp.weixin.qq.com/s/x-GfvPV9nv9beq_Qa0EBtg",
    ],
    "成都中院": [
        "https://mp.weixin.qq.com/s/B_wheJnOoq-2KuclHI9saA",
    ],
    "重庆五中院": [
        "http://mp.weixin.qq.com/s?__biz=Mzg5MzE4MjQxMw==&mid=2247629234&idx=1&sn=3391fe9b39101d49e16336aec5aaa81f",
    ],
    "武汉中院": [
        "https://mp.weixin.qq.com/s/emhYsa5_2MHpEVSjxbr46g",
    ],
    "西安中院": [
        "https://mp.weixin.qq.com/s/cjiJ1ZzsGC-Us9GsMxdErQ",
    ],
    "青岛中院": [
        "http://mp.weixin.qq.com/s?__biz=MzA3MTc1Njg5Ng==&mid=2651734386&idx=1&sn=f45f6983b2e6580b54b152c4c6962cf1",
    ],
    "宁波中院": [
        "https://mp.weixin.qq.com/s/9UTK2a25A8bAw9Q_Jsr6RA",
    ],
    "最高人民法院": [
        "https://mp.weixin.qq.com/s/XCWC_sn05if-ef68_Ddsdg",
    ],
    "最高人民法院司法案例研究院": [
        "http://mp.weixin.qq.com/s?__biz=MzIxNTYzNzU4NA==&mid=2247586491&idx=2&sn=6c598d081a12668802e2b907b4b013ac",
    ],
    "天平阳光": [
        "https://mp.weixin.qq.com/s/ESZoJf8KPNS3Y2i3Cv6J1w",
    ],
    "中国普法": [
        "https://mp.weixin.qq.com/s/0FSevLaRb4bqTjtaU1IwsQ",
    ],
    "最高人民检察院": [
        "https://mp.weixin.qq.com/s/piEVgV88YVydglF5C_XKUQ",
    ],
}
