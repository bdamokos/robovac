"""Tests for protocol v3.4+ bootstrap DPS refresh behavior."""

import json
from unittest.mock import AsyncMock

import pytest

from custom_components.robovac.tuyalocalapi import (
    DPS_BOOTSTRAP_REQUEST_LIMIT,
    Message,
    TuyaDevice,
)
from custom_components.robovac.vacuums.T2277 import T2277
from custom_components.robovac.vacuums.T2320 import T2320


def _device(model_details: type, version: tuple[int, int] = (3, 4)) -> TuyaDevice:
    """Build a TuyaDevice shell without starting background queue tasks."""
    device = TuyaDevice.__new__(TuyaDevice)
    device.device_id = "test-device"
    device.gateway_id = "test-device"
    device.model_details = model_details
    device.version = version
    device._dps = {}
    device._queue = []
    device._listeners = {}
    device._dps_bootstrap_requests = 0
    device.async_connect = AsyncMock()
    return device


def _queued_updatedps_ids(device: TuyaDevice) -> list[int]:
    message = device._queue[-1]
    assert message.command == Message.UPDATEDPS
    return json.loads(message.payload.decode("utf-8"))["dpId"]


def test_bootstrap_dps_request_uses_t2320_state_codes() -> None:
    device = _device(T2320)

    assert device._dps_to_request() == {
        "152": None,
        "153": None,
        "169": None,
        "172": None,
        "173": None,
    }


def test_bootstrap_dps_request_uses_t2277_state_codes_without_rich_telemetry() -> None:
    device = _device(T2277)

    assert device._dps_to_request() == {
        "152": None,
        "153": None,
        "163": None,
        "173": None,
        "177": None,
        "178": None,
    }


@pytest.mark.asyncio
async def test_async_get_requests_bootstrap_dps_when_state_is_missing() -> None:
    device = _device(T2277)

    await device.async_get()

    device.async_connect.assert_awaited_once()
    assert _queued_updatedps_ids(device) == [152, 153, 163, 173, 177, 178]


@pytest.mark.asyncio
async def test_async_get_stops_bootstrap_dps_after_state_arrives() -> None:
    device = _device(T2277)
    device._dps = {"153": "AA=="}

    await device.async_get()

    device.async_connect.assert_awaited_once()
    assert device._queue == []


@pytest.mark.asyncio
async def test_async_get_limits_bootstrap_dps_retries() -> None:
    device = _device(T2277)

    for _ in range(DPS_BOOTSTRAP_REQUEST_LIMIT + 1):
        await device.async_get()

    assert len(device._queue) == DPS_BOOTSTRAP_REQUEST_LIMIT


@pytest.mark.asyncio
async def test_async_get_leaves_legacy_status_path_unchanged() -> None:
    device = _device(T2277, version=(3, 3))
    device.async_receive = AsyncMock(return_value=None)

    await device.async_get()

    assert len(device._queue) == 1
    assert device._queue[0].command == Message.GET_COMMAND
