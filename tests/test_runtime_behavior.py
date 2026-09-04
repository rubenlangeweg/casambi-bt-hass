"""Behavioral tests for reconnect diagnostics wiring."""

# Runtime behavior is intentionally exercised through the integration's private
# callback seams because those are the boundaries registered with Home Assistant.
# ruff: noqa: SLF001

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _api(modules):
    hass = SimpleNamespace(config=SimpleNamespace(config_dir=str(Path.cwd())))
    entry = modules.ConfigEntry()
    return modules.integration.CasambiApi(hass, entry, "AA:BB", "secret")


def test_bluetooth_callback_registration_uses_passive_scanning(
    integration_modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runtime registers its reconnect callback with the expected filter."""
    api = _api(integration_modules)
    calls: list[tuple[object, object, dict[str, object], object]] = []
    cancel = object()

    def register(hass, callback, match_dict, scanning_mode):
        calls.append((hass, callback, match_dict, scanning_mode))
        return cancel

    monkeypatch.setattr(
        integration_modules.bluetooth, "async_register_callback", register
    )

    api._register_bluetooth_callback()

    assert calls == [
        (
            api.hass,
            api._bluetooth_callback,
            {"address": "AA:BB", "connectable": True},
            integration_modules.bluetooth.BluetoothScanningMode.PASSIVE,
        )
    ]
    assert api._cancel_bluetooth_callback is cancel


def test_library_callbacks_are_registered_and_removed_once(integration_modules) -> None:
    """Reconnects must not accumulate duplicate callbacks in the library."""
    api = _api(integration_modules)

    api._register_casa_callbacks()
    api._register_casa_callbacks()

    assert api.casa.disconnect_callbacks == [api._casa_disconnect]
    assert api.casa.unit_changed_handlers == [api._unit_changed_handler]

    api._unregister_casa_callbacks()
    api._unregister_casa_callbacks()

    assert api.casa.disconnect_callbacks == []
    assert api.casa.unit_changed_handlers == []


def test_disconnect_callback_counts_and_schedules_only_once(
    integration_modules,
) -> None:
    """Repeated library callbacks count, but do not create concurrent reconnect tasks."""
    api = _api(integration_modules)

    api._casa_disconnect()
    api._casa_disconnect()

    assert api.connection_diagnostics.disconnects == 2
    assert api.connection_diagnostics.state == "disconnected"
    assert [name for _, name in api.conf_entry.background_tasks] == [
        "Delayed reconnect"
    ]
    for coroutine, _ in api.conf_entry.background_tasks:
        coroutine.close()


@pytest.mark.asyncio
async def test_delayed_reconnect_records_missing_device_without_attempt(
    integration_modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing advertisement is a categorized skip, not a reconnect attempt."""
    api = _api(integration_modules)
    monkeypatch.setattr(integration_modules.integration.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        integration_modules.bluetooth,
        "async_ble_device_from_address",
        lambda *_args, **_kwargs: None,
    )
    api.try_reconnect = AsyncMock()

    await api._delayed_reconnect()

    api.try_reconnect.assert_not_awaited()
    snapshot = api.connection_diagnostics.snapshot()["connection"]
    assert snapshot["reconnect_skips"] == 1
    assert snapshot["last_reconnect_result"] == "skipped_device_not_present"


@pytest.mark.asyncio
async def test_delayed_reconnect_skips_when_connection_recovered(
    integration_modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A connection restored during the delay should not be disturbed."""
    api = _api(integration_modules)
    api.casa.connected = True
    monkeypatch.setattr(integration_modules.integration.asyncio, "sleep", AsyncMock())
    api.try_reconnect = AsyncMock()

    await api._delayed_reconnect()

    api.try_reconnect.assert_not_awaited()
    snapshot = api.connection_diagnostics.snapshot()["connection"]
    assert snapshot["reconnect_attempts"] == 0
    assert snapshot["last_reconnect_result"] == "skipped_already_connected"


@pytest.mark.asyncio
async def test_reconnect_skips_while_an_attempt_holds_the_lock(
    integration_modules,
) -> None:
    """A concurrent callback should not start or release another attempt's lock."""
    api = _api(integration_modules)

    async with api._reconnect_lock:
        await api.try_reconnect()
        assert api._reconnect_lock.locked()

    snapshot = api.connection_diagnostics.snapshot()["connection"]
    assert snapshot["reconnect_attempts"] == 0
    assert snapshot["reconnect_skips"] == 1
    assert snapshot["last_reconnect_result"] == "skipped_already_in_progress"


@pytest.mark.asyncio
async def test_reconnect_failure_logs_category_and_releases_lock(
    integration_modules, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed reconnect retains its safe category and always releases the lock."""
    api = _api(integration_modules)
    api.casa.disconnect = AsyncMock()

    async def fail_connect() -> None:
        api.connection_diagnostics.record_connection_failure("bluetooth")
        raise RuntimeError("sentinel secret must not be logged")

    api.connect = fail_connect

    with caplog.at_level(logging.INFO):
        await api.try_reconnect()

    snapshot = api.connection_diagnostics.snapshot()["connection"]
    assert snapshot["reconnect_attempts"] == 1
    assert snapshot["reconnect_failures"] == 1
    assert api.connection_diagnostics.reconnect_failure_categories == {"bluetooth": 1}
    assert api.connection_diagnostics.last_reconnect_failure_category == "bluetooth"
    assert not api._reconnect_lock.locked()
    assert "reconnect failed (bluetooth)" in caplog.text
    assert "sentinel secret" not in caplog.text


@pytest.mark.asyncio
async def test_successful_reconnect_updates_counters_and_releases_lock(
    integration_modules,
) -> None:
    """A successful reconnect records its outcome after the real reconnect branch."""
    api = _api(integration_modules)
    api.casa.disconnect = AsyncMock()

    async def connect() -> None:
        api.casa.connected = True
        api.connection_diagnostics.record_connected()

    api.connect = connect

    await api.try_reconnect()

    snapshot = api.connection_diagnostics.snapshot()["connection"]
    assert snapshot["reconnect_attempts"] == 1
    assert snapshot["reconnect_successes"] == 1
    assert snapshot["last_reconnect_result"] == "success"
    assert snapshot["state"] == "connected"
    assert not api._reconnect_lock.locked()


def test_last_known_inventory_survives_disconnect_and_failed_reconnect(
    integration_modules,
) -> None:
    """Diagnostics retain the last healthy aggregate inventory while disconnected."""
    api = _api(integration_modules)
    api.casa.units = [object(), object(), object()]
    api.casa.groups = [object()]
    api.casa.scenes = [object(), object()]

    api._refresh_inventory()
    api.connection_diagnostics.record_disconnect()
    api.connection_diagnostics.record_reconnect_attempt()
    api.connection_diagnostics.record_reconnect_failure("unexpected")

    assert api.connection_diagnostics.inventory == {
        "units": 3,
        "groups": 1,
        "scenes": 2,
    }


def test_unsupported_control_mode_is_aggregated_and_rate_limited(
    integration_modules, caplog: pytest.LogCaptureFixture
) -> None:
    """Unsupported modes are surfaced by category without per-device log spam."""
    api = _api(integration_modules)
    pushbutton = SimpleNamespace(
        type=integration_modules.UnitControlType.PUSHBUTTONSTATE
    )
    api.casa.units = [
        SimpleNamespace(unitType=SimpleNamespace(controls=[pushbutton])),
        SimpleNamespace(unitType=SimpleNamespace(controls=[pushbutton])),
    ]

    with caplog.at_level(logging.WARNING):
        api._refresh_unsupported_control_modes()
        api._refresh_unsupported_control_modes()

    assert api.connection_diagnostics.unsupported_control_modes == {
        "PUSHBUTTONSTATE": 2
    }
    assert caplog.text.count("Unsupported Casambi control modes observed") == 1
    assert "PUSHBUTTONSTATE=2" in caplog.text
