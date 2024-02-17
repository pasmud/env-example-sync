import os
from pathlib import Path

import pytest

from env_example_sync.__main__ import main


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("settings.py").write_text(
        "import os\n"
        "os.getenv('DEMO_Z', 'fake-fallback')\n"
        "os.environ.get('DEMO_A')\n"
        "os.environ['DEMO_Z']\n"
    )
    return Path(".env.example")


def sync(*options, target=".env.example"):
    return main(["sync", "--example", target, *options, "settings.py"])


def test_check_never_creates_and_lists_each_missing_key_once(project, capsys):
    assert sync("--check") == 1
    assert not project.exists()
    output = capsys.readouterr()
    assert not output.out
    assert output.err.splitlines() == [
        ".env.example: example does not exist",
        ".env.example: missing DEMO_A (settings.py:3:1)",
        ".env.example: missing DEMO_Z (settings.py:2:1)",
    ]
    assert sync() == 0
    assert project.read_bytes() == b"DEMO_A=\nDEMO_Z=\n"
    assert sync("--check") == 0


def test_append_preserves_comments_order_bom_crlf_and_mode(project):
    original = b"\xef\xbb\xbf# Fake project\r\n\r\n export EXTERNAL_KEY =  # documented elsewhere\r\nDEMO_Z="
    project.write_bytes(original)
    project.chmod(0o640)
    assert sync("--check") == 1
    assert project.read_bytes() == original
    assert sync() == 0
    expected = original + b"\r\nDEMO_A=\r\n"
    assert project.read_bytes() == expected
    info = project.stat()
    assert info.st_mode & 0o777 == 0o640
    assert sync() == sync("--check") == 0
    assert project.stat().st_ino == info.st_ino
    assert project.read_bytes() == expected


@pytest.mark.parametrize(
    "original",
    [b"DEMO=synthetic-value", b"DEMO=\"\"", b"DEMO=#fake-value", b"DEMO=\nDEMO=", b"# \xff", b"DEMO"],
)
def test_malformed_or_populated_examples_are_untouched(project, capsys, original):
    project.write_bytes(original)
    assert sync("--check") == 2
    assert sync() == 2
    assert project.read_bytes() == original
    output = capsys.readouterr()
    assert not output.out
    assert "synthetic-value" not in output.err
    assert "fake-value" not in output.err
    assert output.err.count("error: .env.example:") == 2


def test_unsupported_source_does_not_modify_existing_example(project, capsys):
    project.write_bytes(b"# Fake settings\n")
    Path("settings.py").write_text("import os\nos.environ['DEMO_A']\nos.getenv(computed_name)\n")
    assert sync() == sync("--check") == 1
    assert project.read_bytes() == b"# Fake settings\n"
    assert capsys.readouterr().err.count("settings.py:3:1: unsupported:") == 2


def test_sync_rejects_real_env_name_symlinks_and_hardlinks(project):
    assert sync(target=".env") == 2
    assert not Path(".env").exists()
    same_content = Path("fake-template.txt")
    same_content.write_bytes(b"# Fixture\n")
    project.symlink_to(same_content)
    assert sync() == 2
    project.unlink()
    os.link(same_content, project)
    assert sync() == 2
    assert same_content.read_bytes() == b"# Fixture\n"
