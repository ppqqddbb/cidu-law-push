"""Offline configuration checks that never print credentials or contact services."""

import argparse
import os
from pathlib import Path

from .paths import CONFIG_DIR, LOG_DIR, OUTPUT_DIR, PROJECT_ROOT


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    print(f"Project: {PROJECT_ROOT}")
    print(f"Config:  {CONFIG_DIR}")
    print(f"Output:  {OUTPUT_DIR}")
    print(f"Logs:    {LOG_DIR}")
    try:
        from .settings import DIFY_API_KEY, DIFY_API_URL
        from .knowledge_base import load

        config = load()
        dify = config["dify"]
        checks = {
            "classification API": bool(DIFY_API_KEY and DIFY_API_URL),
            "database configuration": bool(config["database"]),
            "knowledge base API": bool(dify.get("api_key") and dify.get("base_url")),
            "knowledge base target": bool(dify.get("dataset_id") or dify.get("dataset_name")),
        }
    except (OSError, ValueError, KeyError, TypeError):
        print("Configuration: INVALID (check private JSON files and environment variables)")
        return 1
    for label, valid in checks.items():
        print(f"{label}: {'OK' if valid else 'MISSING'}")
    config_path = Path(os.getenv("CASE_DB_CONFIG", CONFIG_DIR / "kb_sync.local.json"))
    print(f"Database/KB config: {config_path.resolve()}")
    print("Offline checks only; remote connectivity and credentials were not verified.")
    return 0 if all(checks.values()) else 1
