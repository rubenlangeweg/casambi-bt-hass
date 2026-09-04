"""Tests for privacy-safe local diagnostics."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1]
TELEMETRY_PATH = ROOT / "custom_components" / "casambi_bt" / "connection_diagnostics.py"
HA_DIAGNOSTICS_PATH = ROOT / "custom_components" / "casambi_bt" / "diagnostics.py"
INTEGRATION_PATH = ROOT / "custom_components" / "casambi_bt" / "__init__.py"


def _load_diagnostics_module():
    spec = spec_from_file_location("casambi_bt_connection_diagnostics", TELEMETRY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    payload = diagnostics_module.build_diagnostics_payload(
        state,
        integration_version="0.2.3",
        library_version="0.3.2",
        cache_version=2,
        unit_count=3,
        group_count=1,
        scene_count=2,
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
        },
        "unsupported_control_modes": {},
        "inventory": {"units": 3, "groups": 1, "scenes": 2},
    }
    serialized = repr(payload).lower()
    assert "password" not in serialized
    assert "address" not in serialized


def test_home_assistant_diagnostics_does_not_read_config_entry_data() -> None:
    """The HA entrypoint should not access stored config entry secrets."""
    source = HA_DIAGNOSTICS_PATH.read_text()

    assert "entry.data" not in source
    assert "CONF_ADDRESS" not in source
    assert "CONF_PASSWORD" not in source


def test_repeated_log_events_are_rate_limited() -> None:
    """Repeated events should be suppressed within the log interval."""
    state = diagnostics_module.ConnectionDiagnostics(log_interval_seconds=300)

    assert state.should_log("reconnect_skipped", now=1000)
    assert not state.should_log("reconnect_skipped", now=1100)
    assert state.should_log("disconnect", now=1100)
    assert state.should_log("reconnect_skipped", now=1300)


def test_api_wires_each_reconnect_outcome_to_diagnostics() -> None:
    """The runtime API should record every reconnect outcome."""
    source = INTEGRATION_PATH.read_text()

    for method_name in (
        "record_disconnect",
        "record_reconnect_attempt",
        "record_reconnect_success",
        "record_reconnect_failure",
        "record_reconnect_skip",
        "set_unsupported_control_modes",
    ):
        assert f"connection_diagnostics.{method_name}" in source
