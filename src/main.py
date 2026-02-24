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
