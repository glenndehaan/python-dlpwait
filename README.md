# DLPWait API Client

An **asynchronous Python client** for fetching real-time **Disneyland Paris park and attraction data** via the DLPWait API.
This lightweight library provides methods for retrieving park hours, attractions, and standby wait times.

## Features

* Asynchronous communication using `aiohttp`
* Fetch park hours and operating schedules
* Fetch attractions
* Get real-time standby wait times
* Built-in error handling for connection and parsing failures
* Designed for easy integration into automation tools or async workflows

## Requirements

* Python **3.11+**
* `aiohttp` library

## Usage Example

```python
import asyncio
from dlpwait import DLPWaitAPI, DLPWaitConnectionError, Parks

async def main():
    client = DLPWaitAPI()

    try:
        await client.update()  # Fetch all park data

        for park in Parks:
            park_data = client.parks[Parks(park)]
            print(f"{park_data.slug} is open from {park_data.opening_time} to {park_data.closing_time}")
            print("Attractions:")
            for attraction_id, name in park_data.attractions.items():
                wait_time = park_data.standby_wait_times.get(attraction_id, "N/A")
                print(f"  {name}: {wait_time} min")

    except DLPWaitConnectionError as err:
        print(f"Error fetching park data: {err}")

    finally:
        await client.close()

asyncio.run(main())
```

## API Reference

### Class: `DLPWaitAPI`

#### Initialization

```python
DLPWaitAPI(session: aiohttp.ClientSession | None = None)
```

* **session** *(optional)* – existing `aiohttp.ClientSession` to reuse.

#### Fetch & Update Methods

| Method     | Description                              |
|------------|------------------------------------------|
| `update()` | Fetch and parse all park data            |
| `close()`  | Close the HTTP session to free resources |

### Models

#### `Parks` Enum

| Member                | Description              |
|-----------------------|--------------------------|
| `DISNEYLAND`          | Disneyland Park          |
| `WALT_DISNEY_STUDIOS` | Walt Disney Studios Park |

#### `Park` Dataclass

| Field                | Type             | Description                                   |
|----------------------|------------------|-----------------------------------------------|
| `slug`               | `Parks`          | Park identifier                               |
| `opening_time`       | `datetime`       | Park opening time                             |
| `closing_time`       | `datetime`       | Park closing time                             |
| `attractions`        | `dict[str, str]` | Attraction IDs mapped to names                |
| `standby_wait_times` | `dict[str, int]` | Attraction IDs mapped to wait times (minutes) |

## Exception Handling

All exceptions inherit from `DLPWaitError`.

| Exception                | Description                                         |
|--------------------------|-----------------------------------------------------|
| `DLPWaitError`           | Base exception for DLPWait client                   |
| `DLPWaitConnectionError` | Connection-related errors (timeouts, bad responses) |

## License

MIT
