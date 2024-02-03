#!/usr/bin/env python3

from asyncio import run, gather
from collections import Counter
from utils import write_to_excel, get_adc_token, get_calls, get_projects
from gcp_operations import make_api_call
from main import *

CALLS = ('vpc_networks', 'firewall_rules', 'subnetworks', 'instances', 'forwarding_rules', 'cloud_routers')
XLSX_FILE = "network_quotas.xlsx"


def sort_data(data: list, key: str, reverse: bool = True) -> list:

    return sorted(data, key=lambda _: _[key], reverse=reverse)


async def main():

    try:
        access_token = await get_adc_token()
        projects = await get_projects(access_token)

    except Exception as e:
        quit(e)

    sheets = {
        'projects': {'description': "Project Counts"},
        'networks': {'description': "Network Counts"},
        'subnets': {'description': "Subnet Counts"},
        'cloud_nats': {'description': "Cloud NAT Counts"},
    }

    # Form a dictionary of relevant API Calls
    _ = await get_calls()
    calls = {k: v.get('calls')[0] for k, v in _.items() if k in CALLS}

    # Get all network data
    network_data = {}
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
        network_data[k] = items

    # Create Lists of objects for any resource that could be relevant to a quota count
    instances = [Instance(_) for _ in network_data.pop('instances')]
    vpc_networks = [Network(_) for _ in network_data.pop('vpc_networks')]
    subnets = [Subnet(_) for _ in network_data.pop('subnetworks')]
    forwarding_rules = [ForwardingRule(_) for _ in network_data.pop('forwarding_rules')]
    cloud_routers = [CloudRouter(_) for _ in network_data.pop('cloud_routers')]
    firewall_rules = [FirewallRule(_) for _ in network_data.pop('firewall_rules')]

    # Use the instances list to form list of all instance NICs
    instance_nics = []
    for instance in instances:
        instance_nics.extend(instance.nics)
    del instances

    network_counts = []
    for vpc_network in vpc_networks:
        network_key = vpc_network.key
        counts = {
            'peerings': vpc_network.peerings,
            'instances': [_ for _ in instance_nics if _.network_key == network_key],
            'forwarding_rules': [_ for _ in forwarding_rules if _.network_key == network_key and _.is_internal],
            'firewall_rules': [_ for _ in firewall_rules if _.network_key == network_key],
            'cloud_routers':  [_ for _ in cloud_routers if _.network_key == network_key],
        }
        application_ilbs = [_ for _ in counts['forwarding_rules'] if _.is_internal and _.is_managed]
        passthrough_ilbs = [_ for _ in counts['forwarding_rules'] if _.is_internal and not _.is_managed]
        network_counts.append({
            'project_id': vpc_network.project_id,
            'key': vpc_network.key,
            'num_subnets': vpc_network.num_subnets,
            'num_peerings': len(counts['peerings']),
            'num_cloud_routers': len(counts['cloud_routers']),
            'num_instances': len(counts['instances']),
            'num_firewall_rules': len(counts['firewall_rules']),
            'application_ilbs': len(application_ilbs),
            'passthrough_ilbs': len(passthrough_ilbs),
        })
    sheets['networks']['data'] = sort_data(network_counts, 'num_instances')

    subnet_counts = []
    for subnet in subnets:
        subnet_key = subnet.key
        counts = {
            'instances': [_ for _ in instance_nics if _.subnet_key == subnet_key],
            'forwarding_rules': [_ for _ in forwarding_rules if _.subnet_key == subnet_key],
        }
        active_ips = len(counts['instances']) + len(counts['forwarding_rules'])
        subnet_counts.append({
            'key': subnet.key,
            'network_name': subnet.network_name,
            'usable_ips': subnet.usable_ips,
            'num_instances': len(counts['instances']),
            'num_forwarding_rules': len(counts['forwarding_rules']),
            'utilization': round(active_ips / subnet.usable_ips * 100),
        })
    sheets['subnets']['data'] = sort_data(subnet_counts, 'num_instances')

    project_counts = []
    for project in projects:
        project_id = project.id
        counts = {
            'networks': [_ for _ in network_counts if _['project_id'] == project_id],
            'firewall_rules': [_ for _ in firewall_rules if _.project_id == project_id],
            'cloud_routers': [_ for _ in cloud_routers if _.project_id == project_id],
        }
        project_counts.append({
            'id': project_id,
            'number': project.number,
            'state': project.state,
            'num_vpc_networks': len(counts['networks']),
            'num_firewall_rules': len(counts['firewall_rules']),
            'num_cloud_routers': len(counts['cloud_routers']),
        })
    sheets['projects']['data'] = sort_data(project_counts, 'num_vpc_networks')

    cloud_nat_counts = []
    for network in network_counts:
        network_key = network['key']
        _ = Counter([nic.region for nic in instance_nics if nic.network_key == network_key])
        for region, instance_count in _.items():
            cloud_nat_counts.append({
                'network_key': network['key'],
                'region': region,
                'num_instances': instance_count,
            })
    sheets['cloud_nats']['data'] = sort_data(cloud_nat_counts, 'num_instances')

    # Create and save the Excel workbook
    _ = await write_to_excel(sheets, XLSX_FILE)

    return sheets

if __name__ == "__main__":

    _ = run(main())
    #print(_)
