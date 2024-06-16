#!/usr/bin/env python3

from asyncio import run, gather
from utils import write_to_excel, get_adc_token, get_calls, get_projects
from gcp_operations import make_api_call
from main import *

CALLS = ('vpc_networks', 'subnetworks', 'instances', 'forwarding_rules')
XLSX_FILE = "empty_subnets.xlsx"


def sort_data(data: list, key: str, reverse: bool = True) -> list:

    return sorted(data, key=lambda _: _[key], reverse=reverse)


async def main():

    try:
        access_token = await get_adc_token()
        projects = await get_projects(access_token)
    except Exception as e:
        quit(e)

    # Form a dictionary of relevant API Calls
    _ = await get_calls()
    calls = {k: v.get('calls')[0] for k, v in _.items() if k in CALLS}

    print("Gathering Network Data...")

    # Get all network data
    raw_data = {}
    for k, call in calls.items():
        # Perform API calls
        urls = [f"/compute/v1/projects/{project.id}/{call}" for project in projects]
        tasks = [make_api_call(url, access_token) for url in urls]
        results = await gather(*tasks)
        results = dict(zip(urls, results))
        items = []
        for url, data in results.items():
            if len(data) > 0:
                _ = [item for item in data]
                items.extend(_)
        raw_data[k] = items

    #print(network_data)

    print("Organizing Network Data...")

    # Create Lists of objects for any resource that could be relevant to a quota count
    network_data = {
        'subnets': [Subnet(_) for _ in raw_data.pop('subnetworks')],
        'instances': [Instance(_) for _ in raw_data.pop('instances')],
        'forwarding_rules': [ForwardingRule(_) for _ in raw_data.pop('forwarding_rules')],
    }

    subnets = [_ for _ in network_data['subnets'] if _.purpose == "PRIVATE"]
    del network_data['subnets']

    forwarding_rules = [_ for _ in network_data['forwarding_rules'] if _.is_internal]
    del network_data['forwarding_rules']

    # Use the instances list to form list of all instance NICs
    instance_nics = []
    for instance in network_data['instances']:
        instance_nics.extend(instance.nics)
    del network_data['instances']

    print("Filtering down to empty subnets...")
    empty_subnets = []
    for subnet in subnets:
        subnet_key = subnet.key
        counts = {
            'instances': [_ for _ in instance_nics if _.subnet_key == subnet_key],
            'forwarding_rules': [_ for _ in forwarding_rules if _.subnet_key == subnet_key],
        }
        if len(counts['instances']) + len(counts['forwarding_rules']) > 0:
            continue
        empty_subnets.append({
            #'key': subnet.key,
            'network_name': subnet.network_name,
            'project_id': subnet.project_id,
            'region': subnet.region,
            'name': subnet.name,
            'cidr_range': subnet.cidr_range,
        })
    empty_subnets = sorted(empty_subnets, key=lambda x: x.get('network_name', "UNKNOWN"), reverse=False)
    return empty_subnets

if __name__ == "__main__":

    from pprint import pprint

    _ = run(main())
    #pprint(_)
    run(write_to_excel({'empty_subnets': {'data': _}}, XLSX_FILE))
