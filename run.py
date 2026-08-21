#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
法律信息爬虫运行入口
用法: python run.py [天数]
示例: python run.py 7  (爬取最近7天的法律信息)
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
    
    # 保存结果（默认不抓取摘要，加 --summary 可开启）
    fetch_summary = "--summary" in sys.argv
    crawler.save_results(fetch_summary=fetch_summary)

    print("\n爬取完成！结果已保存到 law_output.txt")


if __name__ == "__main__":
    main()
