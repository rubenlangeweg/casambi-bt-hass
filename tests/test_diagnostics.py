"""Tests for privacy-safe local diagnostics."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
TELEMETRY_PATH = ROOT / "custom_components" / "casambi_bt" / "connection_diagnostics.py"


def _load_diagnostics_module():
    spec = spec_from_file_location("casambi_bt_connection_diagnostics", TELEMETRY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_absent_recursively(value, forbidden: tuple[str, ...]) -> None:
    """Assert sensitive strings are absent from every key and nested value."""
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_absent_recursively(key, forbidden)
            _assert_absent_recursively(item, forbidden)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _assert_absent_recursively(item, forbidden)
        return
    for sentinel in forbidden:
        assert sentinel not in str(value)


diagnostics_module = _load_diagnostics_module()


def test_reconnect_counters_and_state_are_recorded() -> None:
    """Reconnect outcomes should update aggregate diagnostics."""
    state = diagnostics_module.ConnectionDiagnostics()

    state.record_disconnect()
    state.record_reconnect_attempt()
    state.record_reconnect_failure()
    state.record_reconnect_attempt()
    state.record_reconnect_success()
    state.record_reconnect_skip("device_not_present")

    assert state.snapshot()["connection"] == {
        "state": "connected",
        "disconnects": 1,
        "reconnect_attempts": 2,
        "reconnect_successes": 1,
        "reconnect_failures": 1,
        "reconnect_skips": 1,
        "last_reconnect_result": "skipped_device_not_present",
        "reconnect_failure_categories": {"unexpected": 1},
        "last_reconnect_failure_category": "unexpected",
    }


def test_unsupported_control_modes_are_aggregated_without_device_data() -> None:
    """Unsupported modes should be counted without identifying devices."""
    state = diagnostics_module.ConnectionDiagnostics()

    state.set_unsupported_control_modes(["UNKOWN", "SENSOR", "UNKOWN"])

    assert state.snapshot()["unsupported_control_modes"] == {
        "SENSOR": 1,
        "UNKOWN": 2,
    }


def test_diagnostics_payload_contains_versions_but_no_credentials() -> None:
    """The payload should expose versions and aggregate inventory only."""
    state = diagnostics_module.ConnectionDiagnostics()
    state.record_connected()
    state.set_inventory(units=3, groups=1, scenes=2)

    payload = diagnostics_module.build_diagnostics_payload(
        state,
        integration_version="0.2.3",
        library_version="0.3.2",
        cache_version=2,
    )

    assert payload == {
        "versions": {
            "integration": "0.2.3",
            "library": "0.3.2",
            "cache": 2,
        },
        "connection": {
            "state": "connected",
            "disconnects": 0,
            "reconnect_attempts": 0,
            "reconnect_successes": 0,
            "reconnect_failures": 0,
            "reconnect_skips": 0,
            "last_reconnect_result": None,
            "reconnect_failure_categories": {},
            "last_reconnect_failure_category": None,
        },
        "unsupported_control_modes": {},
        "inventory": {"units": 3, "groups": 1, "scenes": 2},
    }
    serialized = repr(payload).lower()
    assert "password" not in serialized
    assert "address" not in serialized


@pytest.mark.asyncio
async def test_home_assistant_diagnostics_entrypoint_excludes_sensitive_values(
    integration_modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual diagnostics entrypoint returns only aggregate safe fields."""
    modules = integration_modules
    api = SimpleNamespace(
        connection_diagnostics=diagnostics_module.ConnectionDiagnostics()
    )
    api.connection_diagnostics.set_inventory(units=3, groups=1, scenes=2)
    api.connection_diagnostics.set_unsupported_control_modes(["PUSHBUTTONSTATE"])
    entry = modules.ConfigEntry("sentinel-entry-id")
    entry.data = {
        "address": "sentinel-network-address",
        "password": "sentinel-network-password",
        "extra_identifier": "sentinel-private-id",
    }
    hass = SimpleNamespace(data={"casambi_bt": {entry.entry_id: api}})
    monkeypatch.setattr(
        modules.diagnostics,
        "async_get_integration",
        lambda _hass, _domain: _async_value(SimpleNamespace(version="0.2.3")),
    )
    monkeypatch.setattr(modules.diagnostics, "_library_version", lambda: "0.3.2")

    payload = await modules.diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert payload["versions"] == {
        "integration": "0.2.3",
        "library": "0.3.2",
        "cache": 2,
    }
    assert payload["inventory"] == {"units": 3, "groups": 1, "scenes": 2}
    assert payload["unsupported_control_modes"] == {"PUSHBUTTONSTATE": 1}
    _assert_absent_recursively(
        payload,
        (
            "sentinel-entry-id",
            "sentinel-network-address",
            "sentinel-network-password",
            "sentinel-private-id",
        ),
    )


async def _async_value(value):
    return value


def test_repeated_log_events_are_rate_limited() -> None:
    """Repeated events should be suppressed within the log interval."""
    state = diagnostics_module.ConnectionDiagnostics(log_interval_seconds=300)

    assert state.should_log("reconnect_skipped", now=1000)
    assert not state.should_log("reconnect_skipped", now=1100)
    assert state.should_log("disconnect", now=1100)
    assert state.should_log("reconnect_skipped", now=1300)
