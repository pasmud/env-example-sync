import json
from pathlib import Path

import pytest

from env_example_sync.inventory import Inventory, Location, Reference, Unsupported, scan

VECTORS = Path(__file__).with_name("regression_vectors")


@pytest.mark.parametrize("fixture", sorted(VECTORS.glob("*.json")), ids=lambda path: path.stem)
def test_inventory_vector(fixture):
    vector = json.loads(fixture.read_text(encoding="utf-8"))
    path = f"{fixture.stem}.py"
    source = "\n".join(vector["source"])
    references = tuple(Reference(key, Location(path, line, col)) for key, line, col in vector["references"])
    unsupported = tuple(
        Unsupported(Location(path, line, col), reason) for line, col, reason in vector["unsupported"]
    )

    result = scan(source, path)

    assert result == Inventory(references, unsupported), vector["title"]
    assert result.keys == tuple(sorted({reference.key for reference in references})), vector["title"]
