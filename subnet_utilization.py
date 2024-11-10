#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_service_projects, get_instances, get_subnets
from gcp_classes import Subnet, Instance, ForwardingRule


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    project_ids = {p.id: p for p in projects}
    host_project_id = settings.get('host_project_id')
    service_projects = await get_service_projects(host_project_id, access_token)
    print(service_projects)
    session = ClientSession(raise_for_status=False)

    service_projects = [sp for sp in service_projects if project_ids.get(sp)]
    print(f"Found {len(service_projects)} Service Projects after filtering")

    tasks = [get_instances(p, access_token, session) for p in service_projects]
    _ = await gather(*tasks)

    instances = []
    for data in _:
        instances.extend(data)
    #instances = dict(zip(service_projects, _))
    #instances = _
    #instances = [i for i in instances if i.network_name == network]
    used_subnetworks = []
    for i in instances:
        for nic in i.nics:
            used_subnetworks.append(nic.subnet_key)
    #print(used_subnetworks)
    #set([i.subnet_key for i in instances])
    #print(instances)
    #quit()

    #print([i['subnetwork'] for i in instances])
    subnets = await get_subnets(host_project_id, access_token, session)
    subnets = {s.key: s for s in subnets if s.key in used_subnetworks}
    #print(subnet_ids)

    await session.close()
    #subnetworks = {s['id']: s for s in _ if 'subnet1' in s['name']}
    #region = 'northamerica-northeast1'
    #if region:
    #    subnetworks = {s: subnetwork for s, subnetwork in subnetworks.items() if subnetwork['region'] == region}
    #print(f"Found {len(subnetworks)} Subnetworks in Shared VPC Host Project '{host_project_id}'")
    #print(subnetworks)
    #quit()

    matches = {s: [] for s in subnets.keys()}
    for subnet_key, subnet in subnets.items():
        #print(s)
        attached_projects = []
        for instance in instances:
            for nic in instance.nics:
                #print(instance.name, nic.subnet_key)
                if nic.subnet_key == subnet_key:
                    if instance.project_id not in attached_projects:
                        attached_projects.append(instance.project_id)
        #attached_projects = set([i.project_id for i in instances if i. == s])
        #print(subnet_key, attached_projects)
        if len(attached_projects) > 0:
            matches[subnet_key].extend(attached_projects)
            #print(s.split('/')[-1], "attached_projects =", [f"{p}" for p in attached_projects])
    #print("found", len(matches.values) if , "matches!")
    _ = {k: v for k, v in matches.items() if len(v) > 0}

    return matches

if __name__ == "__main__":

    from pprint import pprint

    _ = run(main())
    pprint(_)

