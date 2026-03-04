"""DLPWait Client API."""

from asyncio import TimeoutError
from datetime import datetime
from typing import Any, TypeAlias
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientTimeout

from .exceptions import DLPWaitConnectionError
from .models import Park, Parks

JSON: TypeAlias = dict[str, Any]

GRAPHQL_QUERY = """
query {
  parks {
    slug
    schedules {
      status
      startTime
      endTime
      date
    }
  }
  attractions {
    id
    active
    hide
    status
    name
    park {
      slug
    }
    waitTime {
      standby {
        minutes
      }
    }
  }
}
"""


class DLPWaitAPI:
    """Asynchronous API client for DLPWait."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """DLPWait API Client."""
        self._session: aiohttp.ClientSession = session or aiohttp.ClientSession()

        self.parks: dict[Parks, Park] = {}

    async def _request(self) -> JSON:
        """Handle a request to the DLPWait api."""
        try:
            async with self._session.post(
                    "https://api.dlpwait.com",
                    json={"query": GRAPHQL_QUERY},
                    timeout=ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    raise DLPWaitConnectionError(
                        f"Unexpected response (Status: {response.status})"
                    )

                payload: JSON = await response.json()
                data = payload.get("data")
                if not isinstance(data, dict):
                    raise DLPWaitConnectionError("Invalid API response")

                return data
        except TimeoutError as err:
            raise DLPWaitConnectionError("Timeout while fetching") from err
        except (ClientError, ClientResponseError) as err:
            raise DLPWaitConnectionError(f"Request failed: {err}") from err
        except Exception as err:
            raise DLPWaitConnectionError(f"Unexpected error: {err}") from err

    @staticmethod
    def _parse_park_hours(parks: list[JSON]) -> dict[Parks, tuple[datetime, datetime]]:
        """Return park hours from the API data."""
        result: dict[Parks, tuple[datetime, datetime]] = {}

        for park in parks:
            try:
                slug = Parks(park["slug"])
            except ValueError:
                continue

            for schedule in park["schedules"]:
                if schedule["status"] == "OPERATING":
                    result[slug] = (datetime.strptime(
                        f"{schedule['date']} {schedule['startTime']}",
                        "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=ZoneInfo("Europe/Paris")), datetime.strptime(
                        f"{schedule['date']} {schedule['endTime']}",
                        "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=ZoneInfo("Europe/Paris")))

        return result

    @staticmethod
    def _parse_attractions(attractions: list[JSON]) -> dict[Parks, dict[str, str]]:
        """Return park attractions from the API data."""
        result: dict[Parks, dict[str, str]] = {}

        for attraction in attractions:
            try:
                slug = Parks(attraction["park"]["slug"])
            except ValueError:
                continue

            if attraction["hide"]:
                continue

            if attraction["status"] == "UNDEFINED":
                continue

            result.setdefault(slug, {})
            result[slug][attraction["id"]] = attraction["name"]

        return result

    @staticmethod
    def _parse_standby_wait_times(attractions: list[JSON]) -> dict[Parks, dict[str, int | None]]:
        """Return park wait times from the API data."""
        result: dict[Parks, dict[str, int | None]] = {}

        for attraction in attractions:
            try:
                slug = Parks(attraction["park"]["slug"])
            except ValueError:
                continue

            if attraction["hide"]:
                continue

            if attraction["status"] == "UNDEFINED":
                continue

            if attraction["status"] != "OPERATING":
                result.setdefault(slug, {})
                result[slug][attraction["id"]] = None
                continue

            standby = attraction.get("waitTime", {}).get("standby")
            if not standby:
                continue

            minutes = standby.get("minutes")
            if minutes is None:
                continue

            result.setdefault(slug, {})
            result[slug][attraction["id"]] = minutes

        return result

    async def update(self) -> None:
        """Fetch and parse all park data."""
        data = await self._request()

        park_hours = self._parse_park_hours(data["parks"])
        attractions = self._parse_attractions(data["attractions"])
        standby_wait_times = self._parse_standby_wait_times(data["attractions"])

        self.parks = {}

        for park in Parks:
            self.parks[park] = Park(
                slug=Parks(park),
                opening_time=park_hours[Parks(park)][0],
                closing_time=park_hours[Parks(park)][1],
                attractions=attractions[Parks(park)],
                standby_wait_times=standby_wait_times[Parks(park)],
            )

    async def close(self) -> None:
        """Close open client session."""
        if self._session:
            await self._session.close()
