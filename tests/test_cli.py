import os
import warnings
from pathlib import Path

import pytest

from env_example_sync.__main__ import main


def test_directory_selection_and_stable_inventory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/.cache").mkdir()
    Path("project/.cache/ignored.py").write_text("not ) Python")
    Path("outside.py").write_text("not ) Python")
    Path("project/link.py").symlink_to("../outside.py")
    Path("project/a.py").write_bytes(
        b"# coding: latin-1\nimport os\nos.getenv('DEMO_Z', 'caf\xe9')\n"
        b"raise AssertionError('must never execute')\n"
    )
    Path("project/z.py").write_text("import os\nos.environ['DEMO_A']\nos.getenv('DEMO_Z')\n")

    assert main(["inventory", "project/z.py", "project", "project/../project/a.py"]) == 0
    output = capsys.readouterr()
    assert output.out.splitlines() == [
        "DEMO_A\tproject/z.py:2:1",
        "DEMO_Z\tproject/a.py:3:1",
        "DEMO_Z\tproject/z.py:3:1",
    ]
    assert output.err == ""


def test_diagnostics_are_separate_from_partial_inventory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("synthetic.py").write_text("import os\nos.getenv('DEMO_STATIC')\nos.getenv(name)\n")
    assert main(["inventory", "synthetic.py"]) == 1
    output = capsys.readouterr()
    assert output.out == "DEMO_STATIC\tsynthetic.py:2:1\n"
    assert output.err == "synthetic.py:3:1: unsupported: key is not a literal string\n"


@pytest.mark.parametrize("name", ["absent.py", ".env", ".env.py", "empty", "link.py", "dirlink/demo.py", "hard.py"])
def test_wrong_or_unsafe_sources_are_errors(tmp_path, monkeypatch, capsys, name):
    monkeypatch.chdir(tmp_path)
    Path("empty").mkdir()
    Path("project").mkdir()
    Path("project/demo.py").touch()
    Path("link.py").symlink_to("project/demo.py")
    Path("dirlink").symlink_to("project", target_is_directory=True)
    Path(".env.py").touch()
    os.link("project/demo.py", "hard.py")
    assert main(["inventory", name]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("error: ")


def test_parse_failure_prevents_partial_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("a.py").write_text("import os\nos.getenv('DEMO_A')\n")
    Path("b.py").write_text("fake_default = )\n")
    assert main(["inventory", "a.py", "b.py"]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert output.err.startswith("error: b.py:1:")
    assert "fake_default" not in output.err


@pytest.mark.parametrize("warning_action", ["always", "error"])
def test_parser_warnings_do_not_escape_inventory(tmp_path, monkeypatch, capsys, warning_action):
    monkeypatch.chdir(tmp_path)
    Path("synthetic.py").write_text("import os\n" r"os.getenv('DEMO_KEY', 'fake-default\q')" "\n")

    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter(warning_action)
        assert main(["inventory", "synthetic.py"]) == 0

    assert not emitted
    output = capsys.readouterr()
    assert output.out == "DEMO_KEY\tsynthetic.py:2:1\n"
    assert output.err == ""
