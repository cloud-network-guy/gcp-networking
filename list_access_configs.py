#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings
from itertools import chain
from pprint import pprint
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import Instance


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    urls = [f"/compute/v1/projects/{project.id}/aggregated/instances" for project in projects]
    session = ClientSession(raise_for_status=False)
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    results = [item for item in list(chain(*results)) if item]
    await session.close()
    instances = [Instance(_) for _ in results]

    # Parse the data and form a list of instances using Instance class
    access_configs = []
    for instance in sorted(instances, key=lambda x: x.name):  # Sort by name
        for nic in instance.nics:
            if nic.external_ip_address:
                _ = {k: getattr(nic, k) for k in ('access_config_name', 'access_config_type', 'external_ip_address', 'network_name')}
                _.update({k: getattr(instance, k) for k in ('name', 'project_id', 'region', 'zone')})
                access_configs.append(_)
    return access_configs

if __name__ == "__main__":

    _ = run(main())
    pprint(_)
