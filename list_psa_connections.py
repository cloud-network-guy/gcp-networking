#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import Network, PSAConnection

SERVICES = {
    'netapp': "cloudvolumesgcp-api-network.netapp.com"
}


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)

    session = ClientSession(raise_for_status=False)

    # Get all networks
    urls = [f"https://compute.googleapis.com/compute/v1/projects/{p.id}/global/networks" for p in projects]
    tasks = [get_api_data(session, url, access_token) for url in urls]
    _ = await gather(*tasks)
    _ = [item for items in _ for item in items]  # Flatten results
    _networks = [Network(item) for item in _]

    # Search for peering connections to each service
    networks = []
    for network in _networks:
        for peering in network.peerings:
            for k in list(SERVICES.keys()):
                if k in peering.get('network'):
                    networks.append(network)
    await session.close()

    session = ClientSession(raise_for_status=False)

    urls.clear()
    for service in SERVICES.values():
        for n in networks:
            urls.append(f"https://servicenetworking.googleapis.com/v1/services/{service}/connections?network={n.id}")
    #print(urls)
    tasks = [get_api_data(session, url, access_token) for url in urls]
    _ = await gather(*tasks)
    _ = [item for items in _ for item in items]  # Flatten results
    _psas = [PSAConnection(item) for item in _]
    await session.close()

    return _psas


if __name__ == "__main__":

    from pprint import pprint

    _ = run(main())
    pprint(set([n.network_name for n in _]))
