#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings
from gcp_utils import get_access_token, get_projects, get_service_projects, get_subnets


XLSX_FILE = "gke_ranges.xlsx"

async def main() -> list:

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    # Get Projects and Services Projects
    projects = await get_projects(access_token)
    host_project_id = settings.get('host_project_id')
    print("Getting GKE clusters using Host Project ID: {}".format(host_project_id))
    _ = await get_service_projects(host_project_id, access_token)
    service_projects = [p for p in projects if p.id in _]
    print("Found {} Shared VPC Service Projects".format(len(service_projects)))

    # Start an AIO HTTP Client Session
    session = ClientSession(raise_for_status=False)

    # Get all Subnetworks defined in the Host Network Project
    subnets = await get_subnets(host_project_id, access_token, session=session)
    subnets = [s for s in subnets if s.purpose == "PRIVATE" and len(s.secondary_ranges) > 0]
    subnets = sorted(subnets, key=lambda x: x.key, reverse=False)
    subnets_by_key = {s.key: s for s in subnets}

    # Populate a dictionary of range names
    services_ranges = {}
    for k, v in subnets_by_key.items():
        services_ranges[k] = {r['name']: None for r in v.secondary_ranges if 'gke-services' in r['name']}

    # Get all GKE Clusters
    gke_clusters = []
    tasks = [p.get_gke_clusters(access_token, session) for p in service_projects]
    _ = await gather(*tasks)
    for p in service_projects:
        if p.gke_clusters:
            gke_clusters.extend(p.gke_clusters)

    fields = ('name', 'region', 'creation_timestamp', 'creation', 'subnet_name', 'master_range', 'endpoint_ips', 'pods_range', 'pods_cidr', 'services_cidr')

    data = []
    for gke_cluster in gke_clusters:
        _ = {k: getattr(gke_cluster, k, "unknown") for k in fields}
        _.update({
            'public_endpoint_ip': _['endpoint_ips'][0],
            'private_endpoint_ip': _['endpoint_ips'][1],
        })
        _.pop('endpoint_ips')
        data.append(_)
    data = sorted(data, key=lambda k: k['creation_timestamp'], reverse=True)

    # Populate subnet ranges with the allocated GKE Cluster name
    for gke_cluster in gke_clusters:
        services_range = gke_cluster.services_range
        subnet_key = gke_cluster.subnet_key
        if subnet := subnets_by_key.get(subnet_key):
            if services_range in [_['name'] for _ in subnet.secondary_ranges]:
                services_ranges[subnet_key][services_range] = gke_cluster.id

    range_data = []
    for subnet_key, ranges in services_ranges.items():
        for k, v in ranges.items():
            cluster_name = "FREE"
            if v:
                cluster_name = v.split('/')[-1]
            range_data.append({
                'subnet_key': subnet_key,
                'range_name': k,
                'gke_cluster': cluster_name,
            })
    return range_data


if __name__ == "__main__":

    from pprint import pprint
    from file_utils import write_to_excel


    sheets = {
        'ranges': {'description': "CoreArchive Commercial GKE Clusters"},
    }
    _ = run(main())
    #pprint(_)
    sheets['ranges']['data'] = _

    _ = run(write_to_excel(sheets, XLSX_FILE))
