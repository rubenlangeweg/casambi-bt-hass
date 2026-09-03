"""Packaging guardrail for the forked reconnect-recovery dependency."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "custom_components" / "casambi_bt" / "manifest.json"
LIBRARY_COMMIT = "feabfcfb14b27373c8667046ec339b49be9f9e1e"


def test_manifest_pins_reconnect_recovery_library_commit() -> None:
    manifest = json.loads(MANIFEST.read_text())

    assert (
        f"casambi-bt @ git+https://github.com/rubenlangeweg/casambi-bt.git@{LIBRARY_COMMIT}"
        in manifest["requirements"]
    )
