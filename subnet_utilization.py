#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_service_projects, get_instances, get_subnets


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

    used_subnetworks = []
    for i in instances:
        for nic in i.nics:
            used_subnetworks.append(nic.subnet_key)

    subnets = await get_subnets(host_project_id, access_token, session)
    subnets = {s.key: s for s in subnets if s.key in used_subnetworks}

    await session.close()

    matches = {s: [] for s in subnets.keys()}
    for subnet_key, subnet in subnets.items():
        attached_projects = []
        for instance in instances:
            for nic in instance.nics:
                if nic.subnet_key == subnet_key:
                    if instance.project_id not in attached_projects:
                        attached_projects.append(instance.project_id)
        if len(attached_projects) > 0:
            matches[subnet_key].extend(attached_projects)
    _ = {k: v for k, v in matches.items() if len(v) > 0}

    return matches

if __name__ == "__main__":

    from pprint import pprint

    _ = run(main())
    pprint(_)

