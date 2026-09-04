"""Packaging guardrail for the forked reconnect-recovery dependency."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "custom_components" / "casambi_bt" / "manifest.json"
LIBRARY_REQUIREMENT = (
    "casambi-bt @ git+https://github.com/rubenlangeweg/casambi-bt.git@"
)
LIBRARY_REVISION = "ee6d832c33477d7ca195bdd33ff45478a4032319"


def test_manifest_pins_library_to_immutable_fork_commit() -> None:
    """The manifest should pin the maintained fork to an immutable commit."""
    manifest = json.loads(MANIFEST.read_text())
    requirement = next(
        requirement
        for requirement in manifest["requirements"]
        if requirement.startswith(LIBRARY_REQUIREMENT)
    )
    revision = requirement.removeprefix(LIBRARY_REQUIREMENT)

    assert revision == LIBRARY_REVISION
