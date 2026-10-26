"""Provide the HA import surface without requiring a running HA installation.

The recovery tests use the real integration, casambi-bt and asyncio scheduler.
Only HA's UI/entity plumbing and discovery boundary are replaced here.
"""

from dataclasses import dataclass
from enum import StrEnum
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock


def module(name, **attributes):
    """Install a small, explicit HA module substitute for import-time symbols."""
    result = ModuleType(name)
    result.__dict__.update(attributes)
    sys.modules[name] = result
    return result


class Entity:
    """Entity base used to observe published state and lifecycle cleanup."""

    async def async_added_to_hass(self):
        """Match the HA lifecycle API."""

    async def async_will_remove_from_hass(self):
        """Match the HA lifecycle API."""

    def async_write_ha_state(self):
        """Record what state the entity publishes when notified."""
        self.published.append(getattr(self, "is_on", self.available))


@dataclass
class EntityDescription:
    """Fields needed by the production descriptions imported in these tests."""

    key: str
    name: str | None = None
    device_class: object = None
    entity_category: object = None


class BinarySensorEntity(Entity):
    """Preserve HA's multiple inheritance shape for the actual status sensor."""


class Platform(StrEnum):
    """Platforms exposed by this integration."""

    BINARY_SENSOR = "binary_sensor"
    LIGHT = "light"
    SCENE = "scene"
    NUMBER = "number"


module("homeassistant")
module("homeassistant.components")
module(
    "homeassistant.components.bluetooth",
    async_ble_device_from_address=Mock(return_value=object()),
    async_register_callback=Mock(return_value=Mock()),
    BluetoothScanningMode=Mock(PASSIVE="passive"),
    BluetoothServiceInfoBleak=object,
    BluetoothChange=object,
)
module("homeassistant.config_entries", ConfigEntry=object)
module(
    "homeassistant.const",
    CONF_ADDRESS="address",
    CONF_PASSWORD="password",
    Platform=Platform,
)
module("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
module(
    "homeassistant.exceptions",
    **{
        name: type(name, (Exception,), {})
        for name in (
            "ConfigEntryAuthFailed",
            "ConfigEntryError",
            "ConfigEntryNotReady",
            "HomeAssistantError",
        )
    },
)
module("homeassistant.helpers")
module("homeassistant.helpers.httpx_client", get_async_client=Mock())
module("homeassistant.helpers.device_registry", CONNECTION_BLUETOOTH="bluetooth")
module(
    "homeassistant.helpers.entity",
    Entity=Entity,
    EntityDescription=EntityDescription,
    DeviceInfo=dict,
    EntityCategory=SimpleNamespace(DIAGNOSTIC="diagnostic"),
)
module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
module(
    "homeassistant.components.binary_sensor",
    BinarySensorDeviceClass=SimpleNamespace(CONNECTIVITY="connectivity"),
    BinarySensorEntity=BinarySensorEntity,
    BinarySensorEntityDescription=EntityDescription,
)
