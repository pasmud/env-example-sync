"""Plan and apply append-only changes to a blank .env.example template."""

import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .inventory import KEY
from .paths import InputError, inspect_path, label, require_regular

_ENTRY = re.compile(rf"[ \t]*(?:export[ \t]+)?({KEY.pattern})[ \t]*=(?:[ \t]*|[ \t]+#.*)")


@dataclass(frozen=True)
class ExamplePlan:
    path: Path
    mode: int | None
    missing: tuple[str, ...]
    content: bytes

    @property
    def needs_write(self) -> bool:
        return self.mode is None or bool(self.missing)

    def write(self) -> None:
        if not self.needs_write:
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".env.example.", delete=False) as file:
                temporary = Path(file.name)
                file.write(self.content)
            if self.mode is not None:
                temporary.chmod(self.mode)
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def plan_example(target: Path, keys: tuple[str, ...]) -> ExamplePlan:
    if target.name != ".env.example":
        raise InputError(f"{target}: target must be named .env.example")
    path, info = inspect_path(target, allow_missing=True)
    if info is not None:
        require_regular(path, info)
    original = path.read_bytes() if info is not None else b""
    try:
        text = original.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{label(path)}: example must be UTF-8") from None

    existing = set()
    lines = text.split("\n")
    for number, raw in enumerate(lines, 1):
        line = raw.removesuffix("\r") if number < len(lines) else raw
        if "\r" in line or "\x00" in line:
            raise InputError(f"{label(path)}:{number}: unsupported example line")
        stripped = line.lstrip(" \t")
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENTRY.fullmatch(line)
        if match is None:
            raise InputError(f"{label(path)}:{number}: expected an empty KEY= assignment")
        key = match[1]
        if key in existing:
            raise InputError(f"{label(path)}:{number}: duplicate example key")
        existing.add(key)

    missing = tuple(sorted(set(keys) - existing))
    newline = b"\r\n" if len(lines) > 1 and lines[0].endswith("\r") else b"\n"
    content = original
    if missing:
        if text and not text.endswith("\n"):
            content += newline
        content += b"".join(key.encode("ascii") + b"=" + newline for key in missing)
    mode = stat.S_IMODE(info.st_mode) & 0o777 if info is not None else None
    return ExamplePlan(path, mode, missing, content)
