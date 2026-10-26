"""Exercise real library disconnect ordering with HA's eager task semantics."""

# Recovery needs to reproduce the real client's internal disconnect callback.
# ruff: noqa: SLF001

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from CasambiBt import Casambi
from CasambiBt._client import CasambiClientEvolution
from CasambiBt._constants import ConnectionState
import pytest

from custom_components.casambi_bt import CasambiApi
from custom_components.casambi_bt.binary_sensor import CasambiBinarySensorEntity
from custom_components.casambi_bt.entities import (
    CasambiNetworkEntity,
    CasambiNetworkGroup,
    CasambiUnitEntity,
    TypedEntityDescription,
)


@pytest.fixture
def api(tmp_path):
    """Use the real library, replacing radio I/O at the client boundary."""
    casa = Casambi(cachePath=tmp_path)
    network = SimpleNamespace(_networkRevision=1, protocolVersion=11, units=[])
    casa._casaNetwork = network
    client = CasambiClientEvolution(
        "00:00:00:00:00:01", Mock(), casa._disconnectCallback, network
    )
    client._connectionState = ConnectionState.AUTHENTICATED
    client.disconnect = AsyncMock()
    casa._casaClient = client

    async def connect_client(_device):
        client._connectionState = ConnectionState.AUTHENTICATED

    casa._connectClient = AsyncMock(side_effect=connect_client)
    result = CasambiApi.__new__(CasambiApi)
    result.hass = object()

    def create_background_task(_hass, coro, name, *, eager_start=True):
        return asyncio.Task(
            coro,
            loop=asyncio.get_running_loop(),
            name=name,
            eager_start=eager_start,
        )

    result.conf_entry = SimpleNamespace(
        async_create_background_task=create_background_task
    )
    result.address = client.address
    result._casa = casa
    result._link_up = True
    result._connection_callbacks = []
    result._callback_map = {}
    result._cancel_bluetooth_callback = None
    result._reconnect_task = None
    casa.registerDisconnectCallback(result._casa_disconnect)
    return result


@pytest.mark.asyncio
async def test_disconnect_reconnect_waits_until_library_resets_state(api):
    """A real client callback must reconnect even with HA's eager task default."""
    client = api._casa._casaClient
    client._on_disconnect(None)
    await api._reconnect_task

    api._casa._connectClient.assert_awaited_once()
    client.disconnect.assert_awaited_once()
    assert api.available


@pytest.mark.asyncio
async def test_disconnect_publishes_unavailable_before_library_resets_state(api):
    """Entity callbacks must not publish the library's stale connected value."""
    observed = []
    api.register_connection_updates(lambda: observed.append(api.available))

    api._casa._casaClient._on_disconnect(None)
    assert observed == [False]
    await api._reconnect_task
    assert observed == [False, True]


@pytest.mark.asyncio
async def test_status_sensor_publishes_disconnected_and_connected(api):
    """The diagnostic sensor stays available while reporting the actual link."""
    sensor = CasambiBinarySensorEntity(api, TypedEntityDescription(key="status"))
    sensor.published = []
    await sensor.async_added_to_hass()

    api._casa._casaClient._on_disconnect(None)
    assert sensor.available
    assert sensor.published == [False]
    await api._reconnect_task
    assert sensor.published == [False, True]

    await sensor.async_will_remove_from_hass()
    assert not api._connection_callbacks


@pytest.mark.asyncio
async def test_reconnect_retries_when_client_returns_without_authenticating(api):
    """A returned call is not sufficient proof of a usable Casambi link."""
    attempts = 0

    async def connect_client(_device):
        nonlocal attempts
        attempts += 1
        if attempts > 1:
            api._casa._casaClient._connectionState = ConnectionState.AUTHENTICATED

    api._casa._connectClient = AsyncMock(side_effect=connect_client)
    api._casa._casaClient._connectionState = ConnectionState.NONE
    api._link_up = False

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("custom_components.casambi_bt.RECONNECT_BACKOFF_START", 0)
        await api.reconnect()

    assert attempts == 2
    assert api.available


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entity_type", [CasambiNetworkEntity, CasambiNetworkGroup, CasambiUnitEntity]
)
async def test_all_entity_types_follow_connection_and_remove_callbacks(
    api, entity_type
):
    """Network, group and individual lights all refresh and unsubscribe."""
    unit = SimpleNamespace(deviceId=1, online=True)
    description = TypedEntityDescription(key="test")
    obj = SimpleNamespace(units=[unit]) if entity_type is CasambiNetworkGroup else unit
    entity = entity_type(api, description, obj)
    entity.published = []
    await entity.async_added_to_hass()

    api._casa._casaClient._on_disconnect(None)
    assert entity.published == [False]
    await api._reconnect_task
    assert entity.published == [False, True]

    await entity.async_will_remove_from_hass()
    api._link_up = False
    api._notify_connection_state()
    assert entity.published == [False, True]
