"""Resolve runtime directories independently of the caller's working directory."""

import os
from pathlib import Path


def project_home() -> Path:
    configured = os.getenv("LAW_PUSH_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    package = Path(__file__).resolve().parent
    if package.parent.name == "src":
        return package.parent.parent
    # Wheel deployments set LAW_PUSH_HOME; otherwise use the launch directory.
    return Path.cwd().resolve()


PROJECT_ROOT = project_home()


def runtime_path(variable: str, default: str) -> Path:
    path = Path(os.getenv(variable, default)).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


CONFIG_DIR = runtime_path("LAW_PUSH_CONFIG_DIR", "config")
OUTPUT_DIR = runtime_path("LAW_PUSH_OUTPUT_DIR", "data/output")
LOG_DIR = runtime_path("LAW_PUSH_LOG_DIR", "logs")
