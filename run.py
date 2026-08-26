#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""法律信息爬取和 Dify 分类入口。用法：python run.py [天数]。"""

import sys
import os
from datetime import datetime, timedelta
from config import DEFAULT_DAYS, DIFY_API_KEY, DIFY_API_URL
from run_filter import DifyAgent, run


def main():
    # 解析命令行参数
    days = DEFAULT_DAYS
    
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
    
    api_url = os.getenv("DIFY_API_URL", DIFY_API_URL)
    api_key = os.getenv("DIFY_API_KEY", DIFY_API_KEY)
    if not api_key:
        print("错误：未配置 DIFY_API_KEY")
        sys.exit(1)
    run(days, DifyAgent(api_url, api_key))
    print("\n处理完成，已生成：")
    print("  - result.txt（过滤前的全部爬取结果）")
    print("  - law.txt（过滤后的法律条文）")
    print("  - case.txt（过滤后的法律案例）")


if __name__ == "__main__":
    main()
