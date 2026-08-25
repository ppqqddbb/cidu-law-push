#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
法律信息爬虫运行入口
用法: python run.py [天数]
示例: python run.py 7  (爬取最近7天的法规与最高法案例)
"""

import sys
from datetime import datetime, timedelta
from law_crawler import LawCrawler


def main():
    # 解析命令行参数
    days = 7  # 默认爬取最近7天
    
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print("错误: 天数必须是整数")
            print("用法: python run.py [天数]")
            print("示例: python run.py 7")
            sys.exit(1)
    
    print(f"开始爬取最近 {days} 天的法律信息...")
    print(f"时间范围: {(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')} 至 {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # 创建爬虫实例
    crawler = LawCrawler(days=days)
    
    # 爬取所有网站
    crawler.crawl_all()
    
    # law.txt 仅含五个法规来源，case.txt 仅含最高法配置的案例栏目。
    crawler.save_core_outputs()
    print("\n爬取完成，已生成：")
    print("  - 法律法规：law.txt")
    print("  - 最高人民法院案例：case.txt")


if __name__ == "__main__":
    main()
