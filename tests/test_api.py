"""Tests for the DLPWait api."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from aiohttp import ClientError

from dlpwait.api import DLPWaitAPI
from dlpwait.exceptions import DLPWaitConnectionError
from dlpwait.models import Park, Parks

tz = ZoneInfo("Europe/Paris")

# -------------------------
# Helpers
# -------------------------

class MockResponse:
    """Mock aiohttp response object supporting async context management."""

    def __init__(self, status=200, payload=None, json_side_effect=None):
        """Initialize the mock response."""
        self.status = status
        self._payload = payload or {}
        self._json_side_effect = json_side_effect

    async def json(self):
        """Return JSON payload or raise configured exception."""
        if self._json_side_effect:
            raise self._json_side_effect
        return self._payload

    async def __aenter__(self):
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context manager."""
        pass


def make_session(response: MockResponse = None, side_effect=None):
    """Create a mocked aiohttp session with configurable behavior."""
    session = MagicMock()
    if side_effect:
        session.post.side_effect = side_effect
    else:
        session.post.return_value = response
    return session


# -------------------------
# _request tests
# -------------------------

@pytest.mark.asyncio
async def test_request_success():
    """Ensure _request returns parsed data on successful response."""
    payload = {"data": {"parks": [], "attractions": []}}
    response = MockResponse(status=200, payload=payload)
    session = make_session(response=response)

    api = DLPWaitAPI(session=session)
    result = await api._request()

    assert result == payload["data"]


@pytest.mark.asyncio
async def test_request_non_200_status():
    """Ensure _request raises on non-200 HTTP status."""
    response = MockResponse(status=500)
    session = make_session(response=response)

    api = DLPWaitAPI(session=session)

    with pytest.raises(DLPWaitConnectionError, match="Unexpected response"):
        await api._request()


@pytest.mark.asyncio
async def test_request_invalid_payload():
    """Ensure _request raises when API payload format is invalid."""
    payload = {"data": "invalid"}
    response = MockResponse(status=200, payload=payload)
    session = make_session(response=response)

    api = DLPWaitAPI(session=session)

    with pytest.raises(DLPWaitConnectionError, match="Invalid API response"):
        await api._request()


@pytest.mark.asyncio
async def test_request_timeout():
    """Ensure _request raises connection error on timeout."""
    session = make_session(side_effect=asyncio.TimeoutError())

    api = DLPWaitAPI(session=session)

    with pytest.raises(DLPWaitConnectionError, match="Timeout"):
        await api._request()


@pytest.mark.asyncio
async def test_request_client_error():
    """Ensure _request raises connection error on aiohttp client error."""
    session = make_session(side_effect=ClientError("boom"))

    api = DLPWaitAPI(session=session)

    with pytest.raises(DLPWaitConnectionError, match="Request failed"):
        await api._request()


# -------------------------
# Static parsing methods
# -------------------------

def test_parse_park_hours():
    """Ensure park hours are parsed correctly and invalid parks are ignored."""
    parks = [
        {
            "slug": "disneyland-park",
            "schedules": [
                {
                    "status": "OPERATING",
                    "startTime": "09:00:00",
                    "endTime": "22:00:00",
                    "date": "2026-01-01"
                }
            ],
        },
        {
            "slug": "invalid-park",
            "schedules": [
                {
                    "status": "OPERATING",
                    "startTime": "09:00:00",
                    "endTime": "22:00:00",
                    "date": "2026-01-01"
                }
            ],
        },
    ]

    result = DLPWaitAPI._parse_park_hours(parks)

    assert result == {
        Parks.DISNEYLAND: (
            datetime(2026, 1, 1, 9, 0, tzinfo=tz),
            datetime(2026, 1, 1, 22, 0, tzinfo=tz),
        )
    }


def test_parse_attractions_filters_correctly():
    """Ensure attractions are filtered by active, visible, and operating status."""
    attractions = [
        {
            "id": "1",
            "name": "Big Thunder Mountain",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
        },
        {
            "id": "2",
            "name": "Hidden Ride",
            "active": True,
            "hide": True,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
        },
    ]

    result = DLPWaitAPI._parse_attractions(attractions)

    assert result == {
        Parks.DISNEYLAND: {
            "1": "Big Thunder Mountain"
        }
    }


def test_parse_standby_wait_times_filters_correctly():
    """Ensure standby wait times are parsed and filtered correctly."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
            "waitTime": {"standby": {"minutes": 35}},
        },
        {
            "id": "2",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
            "waitTime": {"standby": None},
        },
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)

    assert result == {
        Parks.DISNEYLAND: {
            "1": 35
        }
    }


# -------------------------
# Additional branch coverage
# -------------------------

def test_parse_attractions_skips_non_operating():
    """Ensure non-operating attractions are ignored."""
    attractions = [
        {
            "id": "1",
            "name": "Closed Ride",
            "active": True,
            "hide": False,
            "status": "DOWN",
            "park": {"slug": "disneyland-park"},
        }
    ]

    result = DLPWaitAPI._parse_attractions(attractions)
    assert result == {}


def test_parse_attractions_skips_inactive():
    """Ensure inactive attractions are ignored."""
    attractions = [
        {
            "id": "1",
            "name": "Inactive Ride",
            "active": False,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
        }
    ]

    result = DLPWaitAPI._parse_attractions(attractions)
    assert result == {}


def test_parse_attractions_skips_invalid_slug():
    """Ensure attractions with invalid park slugs are ignored."""
    attractions = [
        {
            "id": "1",
            "name": "Invalid Park Ride",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "not-a-real-park"},
        }
    ]

    result = DLPWaitAPI._parse_attractions(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_inactive():
    """Ensure inactive attractions are ignored in standby wait times."""
    attractions = [
        {
            "id": "1",
            "active": False,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
            "waitTime": {"standby": {"minutes": 10}},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_hidden():
    """Ensure hidden attractions are ignored in standby wait times."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": True,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
            "waitTime": {"standby": {"minutes": 10}},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_non_operating():
    """Ensure non-operating attractions are ignored in standby wait times."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": False,
            "status": "DOWN",
            "park": {"slug": "disneyland-park"},
            "waitTime": {"standby": {"minutes": 10}},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_invalid_slug():
    """Ensure attractions with invalid park slugs are ignored in standby wait times."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "invalid-park"},
            "waitTime": {"standby": {"minutes": 10}},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_missing_wait_time():
    """Ensure attractions missing waitTime are ignored."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_missing_standby():
    """Ensure attractions missing standby data are ignored."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
            "waitTime": {},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


def test_parse_standby_wait_times_skips_none_minutes():
    """Ensure attractions with None standby minutes are ignored."""
    attractions = [
        {
            "id": "1",
            "active": True,
            "hide": False,
            "status": "OPERATING",
            "park": {"slug": "disneyland-park"},
            "waitTime": {"standby": {"minutes": None}},
        }
    ]

    result = DLPWaitAPI._parse_standby_wait_times(attractions)
    assert result == {}


# -------------------------
# update() integration
# -------------------------

@pytest.mark.asyncio
async def test_update_populates_parks():
    """Ensure update() populates parks with hours and standby wait times."""
    payload = {
        "data": {
            "parks": [
                {
                    "slug": "disneyland-park",
                    "schedules": [
                        {
                            "status": "OPERATING",
                            "startTime": "09:00:00",
                            "endTime": "22:00:00",
                            "date": "2026-01-01"
                        }
                    ],
                },
                {
                    "slug": "walt-disney-studios-park",
                    "schedules": [
                        {
                            "status": "OPERATING",
                            "startTime": "09:30:00",
                            "endTime": "21:00:00",
                            "date": "2026-01-01"
                        }
                    ],
                },
            ],
            "attractions": [
                {
                    "id": "1",
                    "name": "Ride A",
                    "active": True,
                    "hide": False,
                    "status": "OPERATING",
                    "park": {"slug": "disneyland-park"},
                    "waitTime": {"standby": {"minutes": 20}},
                },
                {
                    "id": "2",
                    "name": "Ride B",
                    "active": True,
                    "hide": False,
                    "status": "OPERATING",
                    "park": {"slug": "walt-disney-studios-park"},
                    "waitTime": {"standby": {"minutes": 15}},
                },
            ],
        }
    }

    response = MockResponse(status=200, payload=payload)
    session = make_session(response=response)

    api = DLPWaitAPI(session=session)
    await api.update()

    assert isinstance(api.parks[Parks.DISNEYLAND], Park)
    assert api.parks[Parks.DISNEYLAND].opening_time == datetime(2026, 1, 1, 9, 0, tzinfo=tz)
    assert api.parks[Parks.DISNEYLAND].standby_wait_times["1"] == 20

    assert api.parks[Parks.WALT_DISNEY_STUDIOS].opening_time == datetime(2026, 1, 1, 9, 30, tzinfo=tz)
    assert api.parks[Parks.WALT_DISNEY_STUDIOS].standby_wait_times["2"] == 15


@pytest.mark.asyncio
async def test_close_closes_session():
    """Ensure close() properly closes the aiohttp session."""
    session = MagicMock()
    session.close = AsyncMock()

    api = DLPWaitAPI(session=session)
    await api.close()

    session.close.assert_awaited_once()
