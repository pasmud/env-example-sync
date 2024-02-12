import pytest

from env_example_sync.inventory import Location, SourceSyntaxError, scan


def test_literal_reads_import_aliases_and_locations():
    result = scan(
        "import os as runtime\n"
        "from os import getenv as option, environ as settings\n"
        "value = runtime.getenv('DEMO_REGION', 'fake-default')\n"
        "value = settings['DEMO_REGION']\n"
        "value = settings.get('DEMO_HOST')\n"
        "value = option(key='DEMO_STAGE', default='fake-default')\n"
        "enabled = 'DEMO_FEATURE' not in runtime.environ\n"
        "value = settings.setdefault('DEMO_MODE', 'fake-default')\n",
        "demo.py",
    )
    assert result.keys == ("DEMO_FEATURE", "DEMO_HOST", "DEMO_MODE", "DEMO_REGION", "DEMO_STAGE")
    assert not result.unsupported
    assert [ref.location for ref in result.references if ref.key == "DEMO_REGION"] == [
        Location("demo.py", 3, 9),
        Location("demo.py", 4, 9),
    ]
    assert "fake-default" not in repr(result)


def test_byte_lookups_share_names_with_string_lookups():
    result = scan(
        "import os as runtime\n"
        "from os import getenvb as option, environb as settings\n"
        "runtime.getenvb(b'DEMO_HOST', b'fake-bytes-default')\n"
        "option(key=b'DEMO_PORT')\n"
        "settings[b'DEMO_HOST']\n"
        "runtime.environb.get(b'DEMO_STAGE')\n"
        "settings.setdefault(b'DEMO_MODE', b'fake-bytes-default')\n"
        "b'DEMO_READY' in settings\n"
        "b'DEMO_DEBUG' not in runtime.environb\n"
        "runtime.getenv('DEMO_HOST')\n",
        "bytes.py",
    )
    assert not result.unsupported
    assert result.keys == ("DEMO_DEBUG", "DEMO_HOST", "DEMO_MODE", "DEMO_PORT", "DEMO_READY", "DEMO_STAGE")
    assert [ref.location for ref in result.references if ref.key == "DEMO_HOST"] == [
        Location("bytes.py", line, 1) for line in (3, 5, 10)
    ]
    assert "fake-bytes-default" not in repr(result)


@pytest.mark.parametrize(
    ("expression", "reason"),
    [
        ("os.getenvb(name)", "key is not a bytes literal"),
        ("os.getenvb('DEMO_WRONG_TYPE')", "key is not a bytes literal"),
        ("os.environb.get(b'DEMO_\\xff')", "key is not a portable environment name"),
        ("os.environb[b'DEMO-DASH']", "key is not a portable environment name"),
        ("os.environb[b'DEMO_SET'] = b'fake-assignment'", "environment assignment or deletion"),
        ("os.getenv(b'DEMO_WRONG_TYPE')", "key is not a literal string"),
    ],
)
def test_byte_lookups_only_accept_portable_literal_byte_keys(expression, reason):
    result = scan(f"import os\n{expression}\n", "bytes.py")
    assert not result.references
    assert [(issue.location, issue.reason) for issue in result.unsupported] == [
        (Location("bytes.py", 2, 1), reason)
    ]


def test_unsupported_access_reports_one_location_per_form_and_no_snippets():
    result = scan(
        "import os\n"
        "os.getenv(name)\n"
        "os.environ[f'DEMO_{suffix}']\n"
        "os.environ['DEMO_SET'] = 'fake-assignment'\n"
        "os.getenv('non-portable-fake')\n"
        "mapping = os.environ\n"
        "os.environ.pop('DEMO_POP')\n"
        "os.environb.keys()\n"
        "os.getenv(*items)\n",
        "demo.py",
    )
    assert not result.keys
    assert [item.location.line for item in result.unsupported] == list(range(2, 10))
    assert "non-portable-fake" not in repr(result)
    assert "fake-assignment" not in repr(result)


def test_shadowed_imports_do_not_create_false_names():
    result = scan("import os as runtime\ndef get(runtime):\n    return runtime.getenv('DEMO')\n", "x.py")
    assert not result.keys
    assert result.unsupported[0].reason == "import alias is local, conditional, or rebound"


def test_unrelated_functions_and_strings_are_ignored_but_nested_reads_count():
    result = scan(
        "import os\n"
        "unrelated.getenv('IGNORED')\n"
        "'os.getenv(IGNORED)'\n"
        "os.getenv('DEMO_A', os.environ.get('DEMO_B'))\n",
        "x.py",
    )
    assert result.keys == ("DEMO_A", "DEMO_B")
    assert not result.unsupported


def test_source_error_uses_location_without_the_faulty_line():
    with pytest.raises(SourceSyntaxError, match=r"^demo.py:1:\d+: cannot parse Python source$"):
        scan("fake_sensitive_text = )", "demo.py")
