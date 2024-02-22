"""Synthetic examples of lookups the scanner cannot resolve safely."""

import os


def read_region(profile):
    return os.environ.get(f"DEMO_{profile}_REGION", "fake-region")


def read_timeout():
    from os import getenv as local_setting

    return local_setting("DEMO_TIMEOUT")
