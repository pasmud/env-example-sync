import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = "examples/demo_service"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "env_example_sync", *args],
        cwd=ROOT,
        env={},
        text=True,
        capture_output=True,
        check=False,
    )


def test_demo_inventory_and_committed_example():
    inventory = run_cli("inventory", f"{DEMO}/app")
    assert inventory.returncode == 0, inventory.stderr
    assert inventory.stderr == ""
    assert inventory.stdout.splitlines() == [
        f"DEMO_ENDPOINT\t{DEMO}/app/settings.py:9:21",
        f"DEMO_METRICS\t{DEMO}/app/settings.py:12:28",
        f"DEMO_REGION\t{DEMO}/app/settings.py:10:19",
        f"DEMO_TIMEOUT\t{DEMO}/app/settings.py:11:24",
    ]
    check = run_cli("sync", "--check", "--example", f"{DEMO}/.env.example", f"{DEMO}/app")
    assert check.returncode == 0, check.stderr
    assert check.stdout == f"{DEMO}/.env.example: up to date\n"


def test_demo_drift_round_trip(tmp_path):
    example = tmp_path / ".env.example"
    complete = (ROOT / DEMO / ".env.example").read_bytes()
    drifted = complete.replace(b"DEMO_TIMEOUT=\n", b"")
    example.write_bytes(drifted)
    args = ("--example", str(example), f"{DEMO}/app")
    check = run_cli("sync", "--check", *args)
    assert check.returncode == 1
    assert f"missing DEMO_TIMEOUT ({DEMO}/app/settings.py:11:24)" in check.stderr
    assert example.read_bytes() == drifted
    update = run_cli("sync", *args)
    assert update.returncode == 0, update.stderr
    assert example.read_bytes() == complete
    assert run_cli("sync", "--check", *args).returncode == 0


def test_dynamic_demo_reports_locations_without_expression_or_default_values():
    result = run_cli("inventory", "examples/dynamic_settings.py")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        "examples/dynamic_settings.py:7:12: unsupported: key is not a literal string",
        "examples/dynamic_settings.py:13:12: unsupported: import alias is local, conditional, or rebound",
    ]
