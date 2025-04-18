#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_environments, get_calls
from gcp_utils import get_api_data, get_access_token


async def main():

    try:
        environments = await get_environments()
        for k, v in environments.items():
            print(k, v)
    except Exception as e:
        quit(e)

    calls = await get_calls()
    print("Calls for disks:", calls.get('disks'))

    session = ClientSession(raise_for_status=False)
    tasks = []
    for e, environment in environments.items():
        if not (project := environment.get('network_project')):
            continue
        google_adc_key = environment.get('google_adc_key')
        print("Environment:", e, "ADC Key:", google_adc_key)
        access_token = await get_access_token(google_adc_key, project)
        urls = []
        for k, v in calls.items():
            if k in ['instances', 'disks']:
                for call in v.get('calls', []):
                    urls.append(f"/compute/v1/projects/{project}/{call}")
            tasks.extend([get_api_data(session, url, access_token) for url in urls])

    raw_data = await gather(*tasks)
    print(raw_data)
    await session.close()


    checkpoints = []


if __name__ == "__main__":

    _ = run(main())
