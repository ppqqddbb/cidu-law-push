#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
法律信息爬虫运行入口
用法: python run.py [天数] [--no-filter]
示例: python run.py 7  (爬取最近7天的法律信息，并使用大模型过滤)
      python run.py 7 --no-filter  (只爬取，不过滤)
"""

import sys
from datetime import datetime, timedelta
from law_crawler import LawCrawler
from law_filter import LawFilter
from config import OUTPUT_FILE


def main():
    # 解析命令行参数
    days = 7  # 默认爬取最近7天
    use_filter = "--no-filter" not in sys.argv
    
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print("错误: 天数必须是整数")
            print("用法: python run.py [天数] [--no-filter]")
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
    output_file = crawler.save_results(fetch_summary=fetch_summary)

    print(f"\n爬取完成！结果已保存到 {output_file}")
    
    # 使用大模型进行过滤
    if use_filter:
        print("\n" + "=" * 60)
        print("开始使用大模型过滤结果...")
        print("=" * 60)
        
        filter_instance = LawFilter()
        filter_instance.filter_results(output_file)
        
        print("\n过滤完成！")
        print("  - 法律条文结果: law.txt")
        print("  - 法律案例结果: case.txt")
    else:
        print("\n跳过过滤步骤（使用 --no-filter 参数）")


if __name__ == "__main__":
    main()
