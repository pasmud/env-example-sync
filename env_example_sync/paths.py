"""Validate explicitly selected local input paths before opening them."""

import stat
from os import stat_result
from pathlib import Path

from .inventory import Inventory, scan

_SKIP_DIRS = {"__pycache__", "build", "dist", "node_modules", "site-packages", "venv"}


class InputError(ValueError):
    """An unusable input path or file."""


def label(path: Path) -> str:
    cwd = Path.cwd()
    return str(path.relative_to(cwd) if path.is_relative_to(cwd) else path)


def inspect_path(path: Path, *, allow_missing: bool = False) -> tuple[Path, stat_result | None]:
    path = path.absolute()
    parts = (*reversed(path.parents), path)
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        try:
            info = part.lstat()
        except FileNotFoundError:
            if allow_missing and last:
                return path, None
            raise InputError(f"{label(part)}: path does not exist") from None
        if stat.S_ISLNK(info.st_mode):
            raise InputError(f"{label(part)}: symbolic links are not accepted")
        if not last and not stat.S_ISDIR(info.st_mode):
            raise InputError(f"{label(part)}: expected a directory")
    return path, info


def require_regular(path: Path, info: stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InputError(f"{label(path)}: expected a regular file without hard links")


def _is_python(path: Path) -> bool:
    return path.suffix == ".py" and not path.name.startswith(".env.")


def _discover(root: Path) -> set[Path]:
    found = set()
    pending = [root]
    while pending:
        for path in sorted(pending.pop().iterdir()):
            if path.name.startswith(".") or path.name in _SKIP_DIRS:
                continue
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif not stat.S_ISLNK(info.st_mode) and _is_python(path):
                require_regular(path, info)
                found.add(path)
    return found


def source_paths(inputs: list[Path]) -> tuple[Path, ...]:
    """Expand supplied directories, without following links or searching parent directories."""
    found = set()
    for supplied in inputs:
        path, info = inspect_path(supplied)
        # Normalize '..' only after verifying all components.
        path = path.resolve(strict=True)
        assert info is not None
        if stat.S_ISDIR(info.st_mode):
            discovered = _discover(path)
            if not discovered:
                raise InputError(f"{label(path)}: directory contains no eligible Python sources")
            found.update(discovered)
        else:
            if not _is_python(path):
                raise InputError(f"{label(path)}: expected a .py source file or directory")
            require_regular(path, info)
            found.add(path)
    return tuple(sorted(found))


def inventory_paths(inputs: list[Path]) -> Inventory:
    references = []
    unsupported = []
    for path in source_paths(inputs):
        result = scan(path.read_bytes(), label(path))
        references.extend(result.references)
        unsupported.extend(result.unsupported)
    return Inventory(tuple(sorted(references)), tuple(sorted(unsupported)))
