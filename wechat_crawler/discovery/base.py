# -*- coding: utf-8 -*-
"""文章发现器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class CandidateURL:
    """候选文章 URL"""
    account_name: str
    url: str
    source: str  # 发现来源: sogou, bing, etc.
    title: str = ""
    discovered_at: str = ""
    status: str = "pending"  # pending, fetched, verified, rejected


class BaseDiscovery(ABC):
    """文章发现器基类"""

    @abstractmethod
    def discover(self, account_name: str, aliases: List[str]) -> List[CandidateURL]:
        """
        发现指定公众号的文章 URL。

        Args:
            account_name: 公众号标准名称
            aliases: 公众号别名列表

        Returns:
            候选 URL 列表
        """
        pass
