#!/usr/bin/env python
"""Source-checkout launcher; keeps 'python run_filter.py 30' compatible."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from law_push.cli import COMMANDS, main


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if not arguments or arguments[0] not in {*COMMANDS, "--help", "-h", "--version"}:
        arguments = ["crawl", *arguments]
    raise SystemExit(main(arguments))
