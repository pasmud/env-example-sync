"""Synthetic source for static analysis; run the scanner, not this module."""

import os as platform
from os import getenv as setting


def read_settings():
    return {
        "endpoint": platform.environ["DEMO_ENDPOINT"],
        "region": setting(key="DEMO_REGION", default="fake-region"),
        "timeout": int(platform.environ.get("DEMO_TIMEOUT", "30")),
        "metrics_enabled": "DEMO_METRICS" in platform.environ,
    }
