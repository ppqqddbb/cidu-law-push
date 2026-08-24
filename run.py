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
    # --sdcourt-only is retained as a compatibility alias; both switches now
    # crawl the five configured official court sites.
    courts_only = "--courts-only" in sys.argv or "--sdcourt-only" in sys.argv
    start_value = None
    end_value = None
    for flag, target in (("--start", "start"), ("--end", "end")):
        if flag in sys.argv:
            index = sys.argv.index(flag)
            if index + 1 >= len(sys.argv):
                print(f"错误: {flag} 后需要 YYYY-MM-DD 日期")
                sys.exit(1)
            if target == "start":
                start_value = sys.argv[index + 1]
            else:
                end_value = sys.argv[index + 1]
    
    positional_days = [value for value in sys.argv[1:] if not value.startswith("--")]
    # Remove values belonging to --start/--end from positional parsing.
    positional_days = [value for value in positional_days
                       if value not in {start_value, end_value}]
    if positional_days:
        try:
            days = int(positional_days[0])
        except ValueError:
            print("错误: 天数必须是整数")
            print("用法: python run.py [天数] [--no-filter]")
            print("示例: python run.py 7")
            sys.exit(1)
    
    # 创建爬虫实例
    crawler = LawCrawler(days=days, start_date=start_value, end_date=end_value)
    if start_value or end_value:
        print("开始爬取指定日期范围的法律信息...")
    else:
        print(f"开始爬取最近 {days} 天的法律信息...")
    print(f"时间范围: {crawler.start_date.strftime('%Y-%m-%d')} 至 {crawler.end_date.strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # 官网专项模式只抓取山东高法指导案例；普通模式保留其他法律网站。
    if courts_only:
        crawler.crawl_courts()
        crawler.results.sort(key=lambda x: x.get("date", ""), reverse=True)
    else:
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
