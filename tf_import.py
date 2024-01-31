#!/usr/bin/env python3

from asyncio import run
from gcp_operations import get_adc_token, make_gcp_call, parse_results

PROJECT_ID = "otl-vpc-shared"
WORKSPACE = "otl-vpc-shared"
MODULE = 'hybrid-networking'

CALLS = {
    'google_compute_vpn_tunnel': "aggregated/vpnTunnels",
    #'google_compute_router_interface': "aggregated/routers",
    #'google_compute_router_interface': "",
}


async def main():

    try:
        access_token = await get_adc_token()
    except Exception as e:
        quit(e)

    for resource, call in CALLS.items():
        url = f"/compute/v1/projects/{PROJECT_ID}/{call}"
        results = await make_gcp_call(url, access_token, api_name='compute')
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
