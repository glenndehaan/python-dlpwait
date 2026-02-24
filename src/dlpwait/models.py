"""DLPWait Models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Parks(StrEnum):
    """Parks available within the API."""

    DISNEYLAND = "disneyland-park"
    WALT_DISNEY_STUDIOS = "walt-disney-studios-park"


@dataclass(kw_only=True, frozen=True)
class Park:
    """Park data returned from the API."""

    slug: Parks
    opening_time: datetime
    closing_time: datetime
    attractions: dict[str, str]
    standby_wait_times: dict[str, int]
