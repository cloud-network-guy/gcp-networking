#!/usr/bin/env python3

from asyncio import run, gather
from collections import Counter
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import *

CALLS = ('vpc_networks', 'firewall_rules', 'subnetworks', 'instances', 'forwarding_rules', 'cloud_routers')
XLSX_FILE = "network_quotas.xlsx"


def sort_data(data: list, key: str, reverse: bool = True) -> list:

    return sorted(data, key=lambda _: _[key], reverse=reverse)


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)

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
    raw_data = {}
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
        raw_data[k] = items
    await session.close()

    # Create Lists of objects for any resource that could be relevant to a quota count
    network_data = {
        'instances': [Instance(_) for _ in raw_data.pop('instances')],
        'vpc_networks': [Network(_) for _ in raw_data.pop('vpc_networks')],
        'subnets': [Subnet(_) for _ in raw_data.pop('subnetworks')],
        'forwarding_rules': [ForwardingRule(_) for _ in raw_data.pop('forwarding_rules')],
        'cloud_routers': [CloudRouter(_) for _ in raw_data.pop('cloud_routers')],
        'firewall_rules': [FirewallRule(_) for _ in raw_data.pop('firewall_rules')],
    }
    del raw_data

    # Use the instances list to form list of all instance NICs
    _ = []
    for instance in network_data['instances']:
        _.extend(instance.nics)
    network_data['instance_nics'] = _
    del network_data['instances']

    network_counts = []
    for vpc_network in network_data['vpc_networks']:
        network_key = vpc_network.key
        counts = {
            'peerings': vpc_network.peerings,
            'instances': [_ for _ in network_data['instance_nics'] if _.network_key == network_key],
            'forwarding_rules': [_ for _ in network_data['forwarding_rules'] if _.network_key == network_key and _.is_internal],
            'firewall_rules': [_ for _ in network_data['firewall_rules'] if _.network_key == network_key],
            'cloud_routers':  [_ for _ in network_data['cloud_routers'] if _.network_key == network_key],
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
    for subnet in network_data['subnets']:
        if subnet.is_psc or subnet.is_proxy_only:
            continue
        subnet_key = subnet.key
        counts = {
            'instances': [_ for _ in network_data['instance_nics'] if _.subnet_key == subnet_key],
            'forwarding_rules': [_ for _ in network_data['forwarding_rules'] if _.subnet_key == subnet_key],
        }
        active_ips = len(counts['instances']) + len(counts['forwarding_rules'])
        subnet_counts.append({
            'name': subnet.name,
            'network_name': subnet.network_name,
            'region': subnet.region,
            'cidr_range': subnet.cidr_range,
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
            'firewall_rules': [_ for _ in network_data['firewall_rules'] if _.project_id == project_id],
            'cloud_routers': [_ for _ in network_data['cloud_routers'] if _.project_id == project_id],
        }
        project_counts.append({
            'id': project_id,
            'number': project.number,
            'creation': project.creation,
            'state': project.state,
            'num_vpc_networks': len(counts['networks']),
            'num_firewall_rules': len(counts['firewall_rules']),
            'num_cloud_routers': len(counts['cloud_routers']),
        })
    sheets['projects']['data'] = sort_data(project_counts, 'num_vpc_networks')

    cloud_nat_counts = []
    for network in network_counts:
        network_key = network['key']
        _ = Counter([nic.region for nic in network_data['instance_nics'] if nic.network_key == network_key])
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
