#!/usr/bin/env python3

from os import environ
from asyncio import run
from aiohttp import ClientSession
from gcp_utils import get_access_token, get_api_data

PROJECT_ID = environ.get("GCP_PROJECT_ID")
WORKSPACE = environ.get("TF_WORKSPACE")
MODULE = environ.get("TF_MODULE")

CALLS = {
    'google_compute_vpn_tunnel': "aggregated/vpnTunnels",
    #'google_compute_router_interface': "aggregated/routers",
    #'google_compute_router_interface': "",
}


async def main():

    try:
        access_token = await get_access_token()
    except Exception as e:
        quit(e)

    session = ClientSession(raise_for_status=False)

    for resource, call in CALLS.items():
        url = f"/compute/v1/projects/{PROJECT_ID}/{call}"
        results = get_api_data(session, url, access_token)
        if 'vpn_tunnel' in resource:
            items = parse_results(results, "parse_vpn_tunnels")
        else:
            items = parse_results(results, "parse_cloud_routers")
        for item in items:
            #print(item.get('name'), item.get('region'))
            name = item.get('name')
            region = item.get('region')
            key = f"{PROJECT_ID}:{region}:{name}"
            resource = f"{region}/{name}"
            command = f"terraform import -var-file='{WORKSPACE}.tfvars'"
            command += f" 'module.{MODULE}.{resource}.default[\\\"{key}\\\"]'"
            command += f" {resource}"
            print(command)
        #print(_.keys())
        #quit()
        #for items in _.get('items'):

if __name__ == "__main__":

    _ = run(main())
