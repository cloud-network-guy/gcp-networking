#!/usr/bin/env python3

from asyncio import run
from gcp_operations import get_adc_token, make_gcp_call
import json

MODULE = 'vpc-network'
RESOURCE = 'google_compute_router_nat'
PROJECT_ID = 'otc-vpc-shared'
NETWORK = 'otc-vpc-shared'


def create_import_entry(resource):

    text = ""

    if name := resource.get('name'):
        router = name
        if region := resource.get('region'):
            region = region.split('/')[-1]
        if 'nats' in resource:
            for nat in resource.get('nats', []):
                nat_name = nat.get('name')
        else:
            nat_name = None
        text += "import { \n"
        if region:
            if RESOURCE == 'google_compute_router_nat' and nat_name:
                #text += f"  id = \"{PROJECT_ID}/{region}/{router}/{nat_name}\" \n"
                #text += f"  to = module.{MODULE}.{RESOURCE}.default[\"{PROJECT_ID}/{region}/{router}/{nat_name}\"] \n"
                text += f"  id = \"{PROJECT_ID}/{region}/{nat_name}\" \n"
                text += f"  to = module.{MODULE}.google_compute_address.cloud_nat[\"{PROJECT_ID}/{region}/{nat_name}\"] \n"
            else:
                text += f"  id = \"{PROJECT_ID}/{region}/{name}\" \n"
                text += f"  to = module.{MODULE}.{RESOURCE}.default[\"{PROJECT_ID}/{region}/{name}\"] \n"
        else:
            text += f"  id = \"{PROJECT_ID}/{name}\" \n"
            text += f"  to = module.{MODULE}.{RESOURCE}.default[\"{PROJECT_ID}/{name}\"] \n"
        text += "}\n"

    return text


async def main():

    try:
        access_token = get_adc_token()
    except Exception as e:
        quit(e)

    # Make API Call
    url = f"/compute/v1/projects/{PROJECT_ID}/aggregated/routers"
    results = await make_gcp_call(url, access_token, api_name='compute')

    # Filter for specific network
    items = [item for item in results.get('items', []) if item.get('network').endswith(NETWORK)]

    # Sort by create timestamp so oldest is first
    #items = sorted(items, key=lambda item: item['creationTimestamp'], reverse=False)

    routers = {item.get('region').split('/')[-1]: item for item in items}
    for region, router in routers.items():
        print(create_import_entry(router))

if __name__ == '__main__':

    run(main())

