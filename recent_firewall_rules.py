#!/usr/bin/env python3 

from pprint import pprint
from time import time
from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import FirewallRule

DAYS_THRESHOLD = 14


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    urls = [f"/compute/v1/projects/{p.id}/global/firewalls" for p in projects]
    session = ClientSession(raise_for_status=False)
    tasks = [get_api_data(session, url, access_token) for url in urls]
    _ = await gather(*tasks)
    _ = [item for items in _ for item in items]  # Flatten results
    await session.close()
    firewall_rules = [FirewallRule(_) for _ in _]

    recents = []
    now = int(time())
    for r in firewall_rules:
        if now - r.creation_timestamp < 3600 * 24 * DAYS_THRESHOLD:
            recents.append({k: getattr(r, k) for k in ('project_id','name','creation')})
    return recents

if __name__ == "__main__":

    from pprint import pprint

    _ = run(main())
    pprint(_)
