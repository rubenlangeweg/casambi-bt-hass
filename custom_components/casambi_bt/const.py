"""Constants for the Casambi Bluetooth integration."""

from typing import Final

from CasambiBt import UnitControlType

from homeassistant.const import Platform

DOMAIN: Final = "casambi_bt"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LIGHT, Platform.SCENE, Platform.NUMBER]

CONF_IMPORT_GROUPS: Final = "import_groups"

CASA_LIGHT_CTRL_TYPES: Final[list[UnitControlType]] = [
    UnitControlType.DIMMER,
    UnitControlType.RGB,
    UnitControlType.WHITE,
    UnitControlType.ONOFF,
    UnitControlType.TEMPERATURE,
]

SUPPORTED_CONTROL_TYPES: Final = frozenset(
    (
        *CASA_LIGHT_CTRL_TYPES,
        UnitControlType.VERTICAL,
        UnitControlType.COLORSOURCE,
        UnitControlType.XY,
    )
)
