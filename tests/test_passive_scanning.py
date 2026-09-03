"""Regression guardrail for low-contention reconnect discovery."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "casambi_bt" / "__init__.py"


def test_reconnect_callback_uses_passive_bluetooth_scanning() -> None:
    source = INTEGRATION.read_text()

    assert "bluetooth.BluetoothScanningMode.PASSIVE" in source
