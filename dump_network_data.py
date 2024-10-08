#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import *


XLXS_FILE = "gcp_network_data.xlsx"


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    # Get projects and create first sheet
    projects = await get_projects(access_token, sort_by='create_timestamp')
    if len(projects) < 1:
        quit("Didn't find any projects")
    sheets = {'projects': {'description': "Projects", 'data': [project.__dict__ for project in projects]}}

    # Add the other sheets
    session = ClientSession(raise_for_status=False)
    calls = await get_calls()
    for k, v in calls.items():
        api_name = v.get('api_name', "compute")
        urls = []
        for call in v.get('calls', []):
            if api_name == 'compute':
                urls.extend([f"/compute/v1/projects/{project.id}/{call}" for project in projects])
            if api_name == 'container':
                urls.extend([f"/v1/projects/{project.id}/{call}" for project in projects])
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results = await gather(*tasks)
        results = dict(zip(urls, results))
        data = []
        for result in results.values():
            if len(result) > 0:
                items = [item for item in result]  # Flatten
                for item in items:
                    network_item = GCPNetworkItem(item)
                    if k == 'instances':
                        instance = Instance(item)
                        nic0 = instance.nics[0]  # Get the network information by looking at the first NIC
                        for field in ('network_key', 'network_name', 'subnet_key', 'subnet_name'):
                            setattr(network_item, field, getattr(nic0, field))
                    data.append(network_item)
        new_sheet = {
            k: {
                'description': v.get('description'),
                'data': [row.__dict__ for row in data],  # Convert from object to dictionary
            }
        }
        sheets.update(new_sheet)

    await session.close()
    # Create and save the Excel workbook
    _ = await write_to_excel(sheets, XLXS_FILE)

if __name__ == "__main__":

    _ = run(main())
