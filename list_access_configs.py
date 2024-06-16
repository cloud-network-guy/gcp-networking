#!/usr/bin/env python3

from asyncio import run, gather
from utils import get_adc_token, get_projects
from gcp_operations import make_api_call
from main import Instance


async def main():

    try:
        access_token = await get_adc_token()
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)

    # Get all instances in all projects
    urls = [f"/compute/v1/projects/{project.id}/aggregated/instances" for project in projects]
    tasks = [make_api_call(url, access_token) for url in urls]
    _ = await gather(*tasks)

    # Parse the data and form a list of instances using Instance class
    _ = [item for items in _ for item in items]  # Flatten results
    instances = [Instance(_) for _ in _]
    del _

    for instance in sorted(instances, key=lambda x: x.name):  # Sort by name
        for nic in instance.nics:
            if nic.external_ip_address:
                print(instance.project_id, instance.region, instance.name, nic.access_config_name)

if __name__ == "__main__":

    _ = run(main())
