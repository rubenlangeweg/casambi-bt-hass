"""Diagnostics support for Casambi Bluetooth."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from CasambiBt._cache import CACHE_VERSION

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import CasambiApi
from .connection_diagnostics import build_diagnostics_payload
from .const import DOMAIN


def _library_version() -> str:
    """Return the installed library version."""
    try:
        return version("casambi-bt")
    except PackageNotFoundError:
        return "unknown"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return aggregate diagnostics without credentials or identifiers."""
    integration = await async_get_integration(hass, DOMAIN)
    api: CasambiApi = hass.data[DOMAIN][entry.entry_id]

    return build_diagnostics_payload(
        api.connection_diagnostics,
        integration_version=integration.version or "unknown",
        library_version=_library_version(),
        cache_version=CACHE_VERSION,
    )
