#!/usr/bin/env python3 

from ipaddress import IPv4Address
from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_api_data, get_instances
from gcp_classes import Instance, ForwardingRule, CloudRouter, GKECluster, CloudSQL

CALLS = ('instances', 'forwarding_rules', 'cloud_routers', 'gke_clusters')
COLUMNS = ('ip_address', 'type', 'project_id', 'region', 'name', 'network_key')
SORT_COLUMN = 'ip_address'
CSV_FILE = 'ip_addresses.csv'
XLSX_FILE = "ip_addresses.xlsx"


async def main():
    
    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    calls = await get_calls()

    print("Gathering IP addresses across", len(projects), "projects...")

    ip_addresses = []

    session = ClientSession(raise_for_status=False)
    """"
    call = calls.get('instances').get('calls')[0]
    urls = [f"/compute/v1/projects/{project.id}/{call}" for project in projects]
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    _ = [item for items in results for item in items]  # Flatten results
    instances = [Instance(_) for _ in _]
    """
    print("Getting GCE Instance IPs...")
    tasks = [p.get_instances(access_token) for p in projects]
    _ = await gather(*tasks)
    instances = []
    for p in projects:
        instances.extend(p.instances)
    for instance in instances:
        for nic in instance.nics:
            _ = {k: getattr(instance, k) for k in ('name', 'project_id', 'region')}
            _.update({
                'ip_address': nic.ip_address,
                'type': "GCE Instance NIC",
                'network_key': nic.network_key,
            })
            ip_addresses.append(_)
            if nic.access_config_name:
                _ = {k: getattr(instance, k) for k in ('name', 'project_id', 'region')}
                _.update({
                    'ip_address': nic.external_ip_address,
                    'type': "GCE Instance NAT IP",
                    'network_key': nic.network_key,
                })
                ip_addresses.append(_)

    print("Getting Forwarding_rules...")

    urls = []
    _ = calls.get('forwarding_rules').get('calls')
    for call in _:
        urls.extend([f"/compute/v1/projects/{project.id}/{call}" for project in projects])
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    _ = [item for items in results for item in items]  # Flatten results
    forwarding_rules = [ForwardingRule(_) for _ in _]
    
    """
    tasks = [p.get_forwarding_rules(access_token) for p in projects]
    _ = await gather(*tasks)
    forwarding_rules = []
    for p in projects:
        forwarding_rules.extend(p.forwarding_rules)
    """
    for forwarding_rule in forwarding_rules:
        _ = {k: getattr(forwarding_rule, k) for k in ('name', 'project_id', 'region', 'network_key')}
        _.update({
            'ip_address': forwarding_rule.ip_address,
            'type': "Forwarding Rule",
        })
        ip_addresses.append(_)

    print("Getting Cloud Routers...")
    urls = []
    _ = calls.get('cloud_routers').get('calls')
    for call in _:
        urls.extend([f"/compute/v1/projects/{project.id}/{call}" for project in projects])
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    _ = [item for items in results for item in items]  # Flatten results
    cloud_routers = [CloudRouter(_) for _ in _]

    # Have to use getRouterStatus() to view all Cloud NAT IPs
    for router in cloud_routers:
        if len(router.cloud_nats) == 0:
            continue
        project_id = router.project_id
        url = f"/compute/v1/projects/{project_id}/regions/{router.region}/routers/{router.name}/getRouterStatus"
        try:
            #_ = await make_api_call(call, access_token)
            _ = await get_api_data(session, url, access_token)
        except:
            continue
        for router_status in _:
            nat_ips = []
            if nat_statuses := router_status.get('natStatus'):
                for nat_status in nat_statuses:
                    nat_ips.extend(nat_status.get('autoAllocatedNatIps', []))
                    nat_ips.extend(nat_status.get('userAllocatedNatIps', []))
            for nat_ip in nat_ips:
                _ = {k: getattr(router, k) for k in ('name', 'project_id', 'region', 'network_key')}
                _.update({
                    'ip_address': nat_ip,
                    'type': "Cloud NAT External IP",
                })
                ip_addresses.append(_)

    print("Getting GKE Endpoints...")
    urls = [f"/v1/projects/{project.id}/locations/-/clusters" for project in projects]
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    _ = [item for items in results for item in items]  # Flatten results
    gke_clusters = [GKECluster(_) for _ in _]
    for gke_cluster in gke_clusters:
        for endpoint_ip in gke_cluster.endpoint_ips:
            _ = {k: getattr(gke_cluster, k) for k in ('name', 'project_id', 'region', 'network_key')}
            _.update({
                'ip_address': endpoint_ip,
                'type': "GKE Endpoint",
            })
            ip_addresses.append(_)

    print("Getting Cloud SQL Instances...")
    urls = [f"https://sqladmin.googleapis.com/v1/projects/{project.id}/instances" for project in projects]
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    _ = [item for items in results for item in items]  # Flatten results
    cloud_sqls = [CloudSQL(_) for _ in _]

    await session.close()

    for cloud_sql in cloud_sqls:
        for ip_address in cloud_sql.ip_addresses:
            _ = {k: getattr(cloud_sql, k) for k in ('name', 'project_id', 'region', 'network_key')}
            _.update({
                'ip_address': ip_address,
                'type': "Cloud SQL Instance",
            })
            ip_addresses.append(_)

    ip_addresses = sorted(ip_addresses, key=lambda x: IPv4Address(x.get(SORT_COLUMN, "UNKNOWN")), reverse=False)
    return ip_addresses


if __name__ == "__main__":

    data = []
    _ = run(main())
    for row in _:
        data.append({k: row[k] for k in COLUMNS if row.get(k) is not None})
    del _
    #data = sorted(data, key=lambda x: x.get(SORT_COLUMN, "UNKNOWN"), reverse=False)
    sheets = {
        'ip_addresses': {'description': "IP Addresses", 'data': data},
    }
    _ = run(write_to_excel(sheets, XLSX_FILE))
