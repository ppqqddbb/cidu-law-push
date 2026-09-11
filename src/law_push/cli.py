"""The shared entry point for installed commands and the source checkout."""

import argparse
from importlib import import_module
import logging
import sys

from . import __version__
from .logging_config import configure_logging

COMMANDS = {
    "crawl": ("pipeline", "爬取、分类、导出、入库并同步知识库"),
    "import-cases": ("database", "导入已有 CSV，不重新爬取"),
    "sync-kb": ("knowledge_base", "同步数据库中待处理案例，支持 --dry-run"),
    "push-kingdee": ("case_push", "通过旧金蝶 HTTP 接口推送案例"),
    "check-config": ("diagnostics", "检查本机配置和路径，不访问远端服务"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="law-push", description="法律信息采集与案例同步工具")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (_, description) in COMMANDS.items():
        commands.add_parser(name, help=description, add_help=False)
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        parser.print_help()
        return 0
    # Each command owns its argument validation and help output.
    options = parser.parse_args(arguments[:1])
    try:
        configure_logging()
        module = import_module(f".{COMMANDS[options.command][0]}", package=__package__)
        return module.main(arguments[1:])
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("任务已中断")
        return 130
    except Exception:
        logging.getLogger(__name__).exception("命令执行失败")
        return 1
