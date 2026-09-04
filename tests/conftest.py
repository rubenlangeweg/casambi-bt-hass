"""Shared realistic module stubs for integration unit tests."""

from __future__ import annotations

from enum import Enum, auto
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


class _UnitControlType(Enum):
    DIMMER = auto()
    RGB = auto()
    WHITE = auto()
    ONOFF = auto()
    TEMPERATURE = auto()
    VERTICAL = auto()
    COLORSOURCE = auto()
    XY = auto()
    PUSHBUTTONSTATE = auto()


class _Casambi:
    def __init__(self, _client: object, _cache_dir: Path) -> None:
        self.connected = False
        self.units: list[object] = []
        self.groups: list[object] = []
        self.scenes: list[object] = []
        self.disconnect_callbacks: list[object] = []
        self.unit_changed_handlers: list[object] = []

    def registerDisconnectCallback(self, callback: object) -> None:
        self.disconnect_callbacks.append(callback)

    def registerUnitChangedHandler(self, callback: object) -> None:
        self.unit_changed_handlers.append(callback)

    def unregisterDisconnectCallback(self, callback: object) -> None:
        self.disconnect_callbacks.remove(callback)

    def unregisterUnitChangedHandler(self, callback: object) -> None:
        self.unit_changed_handlers.remove(callback)


class _ConfigEntry:
    def __init__(self, entry_id: str = "entry-id") -> None:
        self.entry_id = entry_id
        self.data: dict[str, str] = {}
        self.background_tasks: list[tuple[object, str]] = []

    def async_create_background_task(
        self, _hass: object, coroutine: object, name: str
    ) -> None:
        self.background_tasks.append((coroutine, name))


def _module(name: str, **attributes: object) -> ModuleType:
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


@pytest.fixture
def integration_modules(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Import the real integration code against narrow runtime stubs."""
    for module_name in tuple(sys.modules):
        if module_name == "custom_components.casambi_bt" or module_name.startswith(
            "custom_components.casambi_bt."
        ):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    class BluetoothError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class NetworkNotFoundError(Exception):
        pass

    class ConfigEntryAuthFailed(Exception):
        pass

    class ConfigEntryError(Exception):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    bluetooth = _module(
        "homeassistant.components.bluetooth",
        BluetoothScanningMode=SimpleNamespace(PASSIVE="passive"),
        async_ble_device_from_address=lambda *_args, **_kwargs: None,
        async_register_callback=lambda *_args, **_kwargs: lambda: None,
    )
    casambi = _module(
        "CasambiBt",
        Casambi=_Casambi,
        Group=object,
        Scene=object,
        Unit=object,
        UnitControlType=_UnitControlType,
    )
    casambi_errors = _module(
        "CasambiBt.errors",
        AuthenticationError=AuthenticationError,
        BluetoothError=BluetoothError,
        NetworkNotFoundError=NetworkNotFoundError,
    )
    casambi_cache = _module("CasambiBt._cache", CACHE_VERSION=2)
    homeassistant = _module("homeassistant")
    components = _module("homeassistant.components", bluetooth=bluetooth)
    config_entries = _module("homeassistant.config_entries", ConfigEntry=_ConfigEntry)
    const = _module(
        "homeassistant.const",
        CONF_ADDRESS="address",
        CONF_PASSWORD="password",
        Platform=SimpleNamespace(
            BINARY_SENSOR="binary_sensor",
            LIGHT="light",
            SCENE="scene",
            NUMBER="number",
        ),
    )
    core = _module(
        "homeassistant.core",
        HomeAssistant=object,
        callback=lambda function: function,
    )
    exceptions = _module(
        "homeassistant.exceptions",
        ConfigEntryAuthFailed=ConfigEntryAuthFailed,
        ConfigEntryError=ConfigEntryError,
        ConfigEntryNotReady=ConfigEntryNotReady,
    )
    helpers = _module("homeassistant.helpers")
    httpx_client = _module(
        "homeassistant.helpers.httpx_client", get_async_client=lambda _hass: object()
    )
    loader = _module(
        "homeassistant.loader",
        async_get_integration=lambda _hass, _domain: None,
    )

    modules = {
        "CasambiBt": casambi,
        "CasambiBt.errors": casambi_errors,
        "CasambiBt._cache": casambi_cache,
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.bluetooth": bluetooth,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.exceptions": exceptions,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.httpx_client": httpx_client,
        "homeassistant.loader": loader,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    integration = importlib.import_module("custom_components.casambi_bt")
    diagnostics = importlib.import_module("custom_components.casambi_bt.diagnostics")
    return SimpleNamespace(
        integration=integration,
        diagnostics=diagnostics,
        bluetooth=bluetooth,
        ConfigEntry=_ConfigEntry,
        UnitControlType=_UnitControlType,
    )
