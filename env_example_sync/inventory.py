"""Inventory recognized os configuration access without executing Python source."""

import ast
import re
from collections import Counter
from dataclasses import dataclass

KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)
_MEMBERS = {"environ", "getenv", "environb", "getenvb"}


@dataclass(frozen=True, order=True)
class Location:
    path: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}:{self.column}"


@dataclass(frozen=True, order=True)
class Reference:
    key: str
    location: Location


@dataclass(frozen=True, order=True)
class Unsupported:
    location: Location
    reason: str


@dataclass(frozen=True)
class Inventory:
    references: tuple[Reference, ...]
    unsupported: tuple[Unsupported, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(sorted({reference.key for reference in self.references}))


class SourceSyntaxError(ValueError):
    """A source could not be parsed; its contents are not part of the error."""


def _bindings(tree: ast.Module) -> tuple[dict[str, str], set[str]]:
    """Resolve direct module imports and retain other imports for diagnostics."""
    aliases = {}
    direct = set(tree.body)
    module_aliases = set()
    seen: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for item in node.names:
                name = item.asname or item.name.split(".", 1)[0]
                seen[name] += 1
                if isinstance(node, ast.Import) and item.name == "os":
                    member = "os"
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "os"
                    and node.level == 0
                    and item.name in _MEMBERS
                ):
                    member = item.name
                else:
                    continue
                if node in direct:
                    aliases[name] = member
                    module_aliases.add(name)
                else:
                    aliases.setdefault(name, member)
        elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            seen[node.id] += 1
        elif isinstance(node, ast.arg):
            seen[node.arg] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen[node.name] += 1
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            seen[node.name] += 1
        elif isinstance(node, ast.MatchMapping) and node.rest:
            seen[node.rest] += 1
    ambiguous = {name for name in aliases if name not in module_aliases or seen[name] != 1}
    return aliases, ambiguous


class _Scanner(ast.NodeVisitor):
    def __init__(self, path: str, tree: ast.Module):
        self.path = path
        self.aliases, self.ambiguous = _bindings(tree)
        self.references: list[Reference] = []
        self.unsupported: list[Unsupported] = []

    def location(self, node: ast.expr) -> Location:
        return Location(self.path, node.lineno, node.col_offset + 1)

    def reject(self, node: ast.expr, reason: str) -> None:
        self.unsupported.append(Unsupported(self.location(node), reason))

    def member(self, node: ast.expr) -> tuple[str, bool]:
        if isinstance(node, ast.Name) and self.aliases.get(node.id) in _MEMBERS:
            return self.aliases[node.id], node.id in self.ambiguous
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _MEMBERS
            and isinstance(node.value, ast.Name)
            and self.aliases.get(node.value.id) == "os"
        ):
            return node.attr, node.value.id in self.ambiguous
        return "", False

    def record(self, node: ast.expr, key: ast.expr | None, ambiguous: bool) -> None:
        if ambiguous:
            self.reject(node, "import alias is local, conditional, or rebound")
        elif not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            self.reject(node, "key is not a literal string")
        elif not KEY.fullmatch(key.value):
            self.reject(node, "key is not a portable environment name")
        else:
            self.references.append(Reference(key.value, self.location(node)))

    def visit_Call(self, node: ast.Call) -> None:
        member, ambiguous = self.member(node.func)
        keyword_key = member == "getenv"
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "setdefault"}:
            member, ambiguous = self.member(node.func.value)
            keyword_key = False
            if member != "environ":
                member = ""
        elif member != "getenv":
            member = ""
        if not member:
            self.generic_visit(node)
            return
        key = node.args[0] if node.args else None
        if key is None and keyword_key:
            key = next((kw.value for kw in node.keywords if kw.arg == "key"), None)
        self.record(node, key, ambiguous)
        for argument in (*node.args, *node.keywords):
            self.visit(argument)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        member, ambiguous = self.member(node.value)
        if member == "environ":
            if isinstance(node.ctx, ast.Load):
                self.record(node, node.slice, ambiguous)
            else:
                self.reject(node, "environment assignment or deletion")
            self.visit(node.slice)
        else:
            self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            member, ambiguous = self.member(node.comparators[0])
            if member == "environ":
                self.record(node, node.left, ambiguous)
                self.visit(node.left)
                return
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.member(node)[0]:
            self.reject(node, "indirect access or unsupported os API")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and self.member(node)[0]:
            self.reject(node, "indirect access or unsupported os API")


def scan(source: str | bytes, path: str) -> Inventory:
    """Return references and unsupported forms; never return source snippets or defaults."""
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError, RecursionError) as exc:
        line = getattr(exc, "lineno", None) or 1
        column = getattr(exc, "offset", None) or 1
        raise SourceSyntaxError(f"{Location(path, line, column)}: cannot parse Python source") from None
    scanner = _Scanner(path, tree)
    try:
        scanner.visit(tree)
    except RecursionError:
        raise SourceSyntaxError(f"{path}: Python source is too deeply nested") from None
    return Inventory(tuple(sorted(scanner.references)), tuple(sorted(scanner.unsupported)))
