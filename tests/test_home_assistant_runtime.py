"""Smoke tests for the supported Home Assistant runtime."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from custom_components.casambi_bt import (
    async_setup_entry,
    async_unload_entry,
    diagnostics,
)
from custom_components.casambi_bt.connection_diagnostics import ConnectionDiagnostics
from homeassistant.components import bluetooth as ha_bluetooth


def test_home_assistant_runtime_imports_integration_entrypoints() -> None:
    """Supported Home Assistant and Casambi packages import the integration."""
    assert inspect.iscoroutinefunction(async_setup_entry)
    assert inspect.iscoroutinefunction(async_unload_entry)
    assert inspect.iscoroutinefunction(diagnostics.async_get_config_entry_diagnostics)
    assert inspect.iscoroutinefunction(ha_bluetooth.async_request_active_scan)


@pytest.mark.asyncio
async def test_home_assistant_runtime_exercises_diagnostics_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the diagnostics entrypoint against the actual runtime imports."""
    state = ConnectionDiagnostics()
    state.set_inventory(units=3, groups=1, scenes=2)
    entry = SimpleNamespace(entry_id="runtime-smoke-entry")
    hass = SimpleNamespace(
        data={
            "casambi_bt": {
                entry.entry_id: SimpleNamespace(connection_diagnostics=state)
            }
        }
    )

    async def get_integration(_hass, _domain):
        return SimpleNamespace(version="0.2.3")

    monkeypatch.setattr(diagnostics, "async_get_integration", get_integration)
    payload = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert payload["inventory"] == {"units": 3, "groups": 1, "scenes": 2}
    assert payload["versions"]["integration"] == "0.2.3"
    assert payload["versions"]["library"] == "0.3.3"
