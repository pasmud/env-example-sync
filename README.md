# env-example-sync

Inventory Python configuration keys and keep a public `.env.example` complete. The scanner uses
Python's AST: it does not execute project code, inspect the process environment, open real `.env`
files, or print source snippets or literal defaults. It has no runtime dependencies beyond Python 3.11+.

## Try it locally

From the repository root, use the bundled synthetic service and its blank template:

```sh
python -m env_example_sync inventory examples/demo_service/app
python -m env_example_sync sync --check --example examples/demo_service/.env.example examples/demo_service/app
```

Install from this checkout with `python -m pip install .` in your own virtual environment to use
the `env-example-sync` command instead of `python -m env_example_sync`.

Inventory prints one `KEY<TAB>PATH:LINE:COLUMN` row per recognized lookup, sorted by key, then
location. For example, `DEMO_ENDPOINT` is referenced at `examples/demo_service/app/settings.py:9:21`.
Paths beneath the working directory are relative; other paths are absolute. Lines and columns are
one-based; lookup columns count UTF-8 bytes, as in Python's AST.

To see a check fail, remove `DEMO_TIMEOUT=` from the synthetic template and rerun the check. It
reports the missing key and its first source location without modifying the file. Restore the key
by running the same command without `--check`. To see unsupported access diagnostics, run:

```sh
python -m env_example_sync inventory examples/dynamic_settings.py
```

## Input and output rules

- Both subcommands require one or more explicit `.py` files or directories. Directories are searched
  recursively for `.py` files, skipping hidden entries, symlinks and `__pycache__`, `build`, `dist`,
  `node_modules`, `site-packages` and `venv`. An explicitly selected directory with no eligible
  sources is an error. Overlapping inputs are deduplicated. Explicit paths cannot traverse symlinks;
  hard-linked and nonregular files are refused. Python source encoding declarations are honored.
- `sync` requires `--example PATH`, whose final component must be exactly `.env.example`. Its
  parent must already exist. Existing templates must be UTF-8 and contain only blank lines,
  comments and empty assignments (`KEY=`, optionally with `export`, horizontal spacing, or an
  inline `#` comment separated from `=` by whitespace). Populated or quoted values, duplicate
  keys and other syntax are rejected without printing the line or changing the file.
- `sync` creates a missing template and appends missing `KEY=` lines in sorted order. It preserves
  existing bytes and leaves extra keys in place for launchers or other code outside the scan.
  New lines use the first existing line ending (LF or CRLF), or LF if there is none. Updates use
  atomic replacement; an up-to-date file is not rewritten. Only select public templates: existing
  comments are preserved verbatim. Run against a stable local checkout, without concurrent edits.
- `sync --check` never writes. A missing file is drift even if no keys were found. Extra blank
  keys do not count as drift. Either sync mode stops on detected unsupported access before
  opening the template, since it cannot verify completeness for those sources.

| Exit | Meaning |
| --- | --- |
| `0` | Inventory completed; sync succeeded or the example was already up to date. |
| `1` | Unsupported access was detected, or the example is missing/incomplete in check mode. Inventory still prints known keys. |
| `2` | Invalid arguments, path, Python syntax, example syntax, or filesystem error. |

Inventory and sync success messages go to stdout. Drift, unsupported access and errors go to stderr.

## Supported Python syntax

The scanner recognizes these forms through direct module-level `import os` and
`from os import environ, getenv`, including `as` aliases:

| Form | Synthetic example |
| --- | --- |
| `getenv` with a first positional argument or `key=` | `os.getenv(key="DEMO_REGION", default="fake-region")` |
| Environment subscript reads | `os.environ["DEMO_ENDPOINT"]` |
| Environment mapping lookups | `os.environ.get("DEMO_TIMEOUT")`, `os.environ.setdefault("DEMO_MODE", "fake-mode")` |
| Single membership tests | `"DEMO_METRICS" in os.environ`, `"DEMO_DEBUG" not in os.environ` |

Keys must be literal strings matching `[A-Za-z_][A-Za-z0-9_]*`. The scanner reports variables,
f-strings, computed keys, writes, indirect references such as `mapping = os.environ`, and other
operations on recognized members as unsupported. Local, conditional and multiply bound import
aliases are conservatively flagged; an unrelated binding of the same name anywhere in a file can
make an alias ambiguous. The tool does not resolve wildcard imports, reflection, wrappers or
third-party configuration libraries and cannot prove it found every runtime lookup. It scans all
branches syntactically without trying to establish what runs.

## Development

In a local virtual environment from the repository root:

```sh
python -m pip install '.[test]'
python -m pytest -q
ruff check .
```

CI runs on pushes and pull requests and checks the synthetic template with the installed command.
This project is licensed under the [MIT License](LICENSE).
