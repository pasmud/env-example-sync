"""Command-line entry point for env-example-sync."""

import argparse
import sys
from pathlib import Path

from .example import plan_example
from .inventory import Inventory, SourceSyntaxError
from .paths import InputError, inventory_paths, label


def _report_unsupported(result: Inventory) -> int:
    for problem in result.unsupported:
        print(f"{problem.location}: unsupported: {problem.reason}", file=sys.stderr)
    return int(bool(result.unsupported))


def _sync(result: Inventory, target: Path, check: bool) -> int:
    if _report_unsupported(result):
        return 1
    plan = plan_example(target, result.keys)
    name = label(plan.path)
    if check and plan.needs_write:
        if plan.mode is None:
            print(f"{name}: example does not exist", file=sys.stderr)
        missing = set(plan.missing)
        reported = set()
        for reference in result.references:
            if reference.key in missing and reference.key not in reported:
                print(f"{name}: missing {reference.key} ({reference.location})", file=sys.stderr)
                reported.add(reference.key)
        return 1
    if plan.needs_write:
        plan.write()
        print(f"{name}: added {len(plan.missing)} blank key(s)")
    else:
        print(f"{name}: up to date")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="env-example-sync", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    inventory = actions.add_parser("inventory", help="list keys with Python source locations")
    inventory.add_argument("sources", metavar="SOURCE", type=Path, nargs="+")
    sync = actions.add_parser("sync", help="append missing blank keys to an example")
    sync.add_argument("--example", required=True, metavar="PATH", type=Path, help="explicit .env.example path")
    sync.add_argument("--check", action="store_true", help="report drift without writing")
    sync.add_argument("sources", metavar="SOURCE", type=Path, nargs="+")
    args = parser.parse_args(argv)

    try:
        result = inventory_paths(args.sources)
        if args.action == "sync":
            return _sync(result, args.example, args.check)
    except (InputError, SourceSyntaxError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for reference in result.references:
        print(f"{reference.key}\t{reference.location}")
    return _report_unsupported(result)


if __name__ == "__main__":
    raise SystemExit(main())
