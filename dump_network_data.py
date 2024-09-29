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
    calls = await get_calls()

    network_data = {}
    session = ClientSession(raise_for_status=False)
    for k, call in calls.items():
        # Perform API calls
        urls = [f"/compute/v1/projects/{project.id}/{call}" for project in projects]
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results = await gather(*tasks)
        results = dict(zip(urls, results))
        items = []
        for url, data in results.items():
            if len(data) > 0:
                _ = [item for item in data]
                items.extend(_)
        network_data[k] = items

    for k, v in calls.items():
        urls = []
        # For each project ID, get network data
        for call in v.get('calls', []):
            urls.extend([f"/compute/v1/projects/{project.id}/{call}" for project in projects])
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results = await gather(*tasks)
        data = []
        for results in results:
            items = [GCPNetworkItem(item) for item in results]
            data.extend([_.__dict__ for _ in items])

        # Add a new sheet with its data
        #print(data)
        new_sheet = {k: {'description': v.get('description'), 'data': data}}
        sheets.update(new_sheet)

    await session.close()
    # Create and save the Excel workbook
    _ = await write_to_excel(sheets, XLXS_FILE)

if __name__ == "__main__":

    _ = run(main())
