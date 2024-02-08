"""Command-line entry point for env-example-sync."""

import argparse
import sys
from pathlib import Path

from .inventory import SourceSyntaxError
from .paths import InputError, inventory_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="env-example-sync", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    inventory = actions.add_parser("inventory", help="list keys with Python source locations")
    inventory.add_argument("sources", metavar="SOURCE", type=Path, nargs="+")
    args = parser.parse_args(argv)

    try:
        result = inventory_paths(args.sources)
    except (InputError, SourceSyntaxError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for reference in result.references:
        print(f"{reference.key}\t{reference.location}")
    for problem in result.unsupported:
        print(f"{problem.location}: unsupported: {problem.reason}", file=sys.stderr)
    return int(bool(result.unsupported))


if __name__ == "__main__":
    raise SystemExit(main())
