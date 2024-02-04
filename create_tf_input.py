#!/usr/bin/env python3

from asyncio import run
from utils import get_adc_token
from gcp_operations import make_gcp_call


def create_import_entry(module, resource, project_id):

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
            if resource == 'google_compute_router_nat' and nat_name:
                text += f"  id = \"{project_id}/{region}/{nat_name}\" \n"
                text += f"  to = module.{module}.google_compute_address.cloud_nat[\"{project_id}/{region}/{nat_name}\"] \n"
            else:
                text += f"  id = \"{project_id}/{region}/{name}\" \n"
                text += f"  to = module.{module}.{resource}.default[\"{project_id}/{region}/{name}\"] \n"
        else:
            text += f"  id = \"{project_id}/{name}\" \n"
            text += f"  to = module.{module}.{resource}.default[\"{project_id}/{name}\"] \n"
        text += "}\n"

    return text


async def main(module, resource, project_id, network):

    try:
        access_token = await get_adc_token()
    except Exception as e:
        quit(e)

    # Make API Call
    url = f"/compute/v1/projects/{project_id}/aggregated/routers"
    results = await make_gcp_call(url, access_token, api_name='compute')

    # Filter for specific network
    items = [item for item in results.get('items', []) if item.get('network').endswith(network)]

    # Sort by create timestamp so oldest is first
    #items = sorted(items, key=lambda item: item['creationTimestamp'], reverse=False)

    routers = {item.get('region').split('/')[-1]: item for item in items}
    for region, router in routers.items():
        print(create_import_entry(router))


if __name__ == '__main__':

    from sys import argv
    from traceback import format_exc

    try:
        arg_names = ['module', 'resource', 'project_id', 'network']
        if len(argv) > len(arg_names):
            args = [argv[i+1] for i, v in enumerate(arg_names)]
            run(main(args[0], args[1], args[2], args[3]))
        else:
            message = f"Usage: {argv[0]}"
            for arg_name in arg_names:
                message += f" <{arg_name}>"
            quit(message)
    except Exception as e:
        quit(format_exc())
