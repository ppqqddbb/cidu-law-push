# -*- coding: utf-8 -*-
"""文章解析器 - 公众号识别、时间过滤"""

import re
from datetime import date, datetime
from typing import List, Optional

from ..config import DATE_RE


class ArticleParser:
    """解析和验证文章"""

    def __init__(self, accounts_config: list):
        """
        Args:
            accounts_config: 公众号配置列表，每项包含 name 和 aliases
        """
        self.accounts = {}
        for acc in accounts_config:
            name = acc["name"]
            aliases = [a.lower() for a in acc.get("aliases", [name])]
            aliases.append(name.lower())
            self.accounts[name] = {
                "name": name,
                "aliases": list(set(aliases)),
            }

    def match_account(self, page_account: str) -> Optional[str]:
        """
        验证文章页面的公众号名称是否匹配配置的公众号。

        Returns:
            匹配的标准名称，或 None
        """
        if not page_account:
            return None
        page_lower = page_account.lower().strip()
        for name, info in self.accounts.items():
            if page_lower in info["aliases"]:
                return name
        return None

    def parse_publish_time(self, time_str: str) -> Optional[date]:
        """解析发布时间字符串为 date 对象"""
        if not time_str:
            return None
        time_str = time_str.replace("-", "/")
        match = DATE_RE.search(time_str)
        if not match:
            return None
        try:
            if match.group(1):
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            today = date.today()
            return date(today.year, int(match.group(4)), int(match.group(5)))
        except ValueError:
            return None

    def is_in_range(self, time_str: str, start: date, end: date) -> bool:
        """检查发布时间是否在指定范围内"""
        pub_date = self.parse_publish_time(time_str)
        if pub_date is None:
            return False
        return start <= pub_date <= end
