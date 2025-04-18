#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from google.oauth2 import service_account
from pathlib import Path
from pprint import pprint
from platform import system
from time import time
import google.auth
import google.auth.transport.requests
import google.oauth2
import yaml
import json

SETTINGS_FILE = "./environments.toml"
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
COMPUTE_API_BASE = "https://www.googleapis.com/compute/v1"


async def get_settings(file_name: str = SETTINGS_FILE) -> dict:

    with open(file_name, mode="rb") as fp:
        return yaml.load(fp, Loader=yaml.FullLoader)


async def read_service_account_key(file: str) -> str:

    try:
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(file, scopes=SCOPES)
        _ = google.auth.transport.requests.Request()
        credentials.refresh(_)
        return credentials.token
    except Exception as e:
        raise e


async def get_adc_token(quota_project_id: str = None) -> str:

    try:
        credentials, project_id = google.auth.default(scopes=SCOPES, quota_project_id=quota_project_id)
        _ = google.auth.transport.requests.Request()
        credentials.refresh(_)
        return credentials.token  # return access token
    except Exception as e:
        raise e


async def get_api_data(url: str, access_token: str, params: dict = None) -> list:

    if 'compute' in url:
        api_name = "compute"
    elif 'clusters' in url:
        api_name = "container"
    else:
        api_name = "unknown"

    if api_name in ['compute']:
        if 'aggregated/' in url or 'global/' in url:
            items_key = 'items'
        elif 'regions/' in url:
            items_key = 'result'
        else:
            items_key = 'resources'
    else:
        items_key = url.split("/")[-1]

    headers = {'Authorization': f"Bearer {access_token}"}

    data = []
    params = {} if not params else params
    try:
        async with ClientSession(raise_for_status=True) as session:
            while True:
                async with session.get(url, headers=headers, params=params, verify_ssl=True) as response:
                    if int(response.status) == 200:
                        json_data = await response.json()
                        if items := json_data.get(items_key):
                            if items_key == 'result':
                                items = [items]
                            if 'aggregated/' in url:
                                _ = []
                                # With aggregated results, we have to walk each region to get the items
                                for k, v in items.items():
                                    aggregated_key = url.split("/")[-1]
                                    _.extend(v.get(aggregated_key, []))
                                items = _
                            data.extend(items)
                        else:
                            if json_data.get('name'):
                                data.append(json_data)
                        # Check for nextPageToken; if so, update the parameters to get the next page
                        if next_page_token := json_data.get('nextPageToken'):
                            params.update({'pageToken': next_page_token})
                        else:
                            break
                    else:
                        raise f"Invalid response: {str(response)}"
        return data

    except Exception as e:
        await session.close()    # Something went wrong when opening the session; don't leave it hanging
        raise e


async def get_projects(access_token: str) -> list:

    try:
        url = "https://cloudresourcemanager.googleapis.com/v1/projects"
        params = {'filter': "lifecycleState: ACTIVE"}
        data = await get_api_data(url, access_token, params)
        projects = []
        for item in data:
            project = {
                'name': item.get('name'),
                'id': item.get('projectId'),
                'number': item.get('projectNumber'),
            }
            projects.append(project)
        return projects

    except Exception as e:
        raise e


async def get_project(project_id: str, access_token: str) -> dict:

    try:
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}"
        params = {'filter': "lifecycleState: ACTIVE"}
        data = await get_api_data(url, access_token, params)
        return {}
    except Exception as e:
        raise e


async def get_shared_vpc_service_projects(host_project_id: str, access_token: str) -> list:

    try:
        url = f"{COMPUTE_API_BASE}/projects/{host_project_id}/getXpnResources"
        data = await get_api_data(url, access_token)
        #print(data)
        return [p['id'] for p in data if p.get('type') == "PROJECT"]

    except Exception as e:
        raise e


async def get_networks(project_id: str, access_token: str) -> list:

    networks = []

    try:
        url = f"{COMPUTE_API_BASE}/projects/{project_id}/global/networks"
        data = await get_api_data(url, access_token)
        for item in data:
            network = {
                'project_id:': project_id,
                'name': item['name'],
                'id': item['selfLink'].replace(f"{COMPUTE_API_BASE}/", ""),
            }
            subnets = []
            for s in item.get('subnetworks', []):
                _ = s.split('/')
                region = _[-3]
                name = _[-1]
                subnet = {
                    'project_id': project_id,
                    'region': region,
                    'name': name,
                    'id': s.replace(f"{COMPUTE_API_BASE}/", ""),
                }
                subnets.append(subnet)
            network.update({'subnets': subnets})
            networks.append(network)
        return networks
    except Exception as e:
        raise e


async def get_subnets(project_id: str, access_token: str, regions: list = None) -> list:

    subnets = []

    try:
        url = f"{COMPUTE_API_BASE}/projects/{project_id}/aggregated/subnetworks"
        data = await get_api_data(url, access_token)
        for item in data:
            if item['purpose'] != "PRIVATE":
                continue
            region = item['region'].split("/")[-1]
            name = item['name']
            ranges = []
            for r in item.get('secondaryIpRanges', []):
                ranges.append({
                    'name': r.get('rangeName'),
                    'cidr': r.get('ipCidrRange'),
                    'gke_cluster': None,
                })
            subnet = {
                'project_id': project_id,
                'region': region,
                'name': name,
                'id': f"projects/{project_id}/regions/{region}/subnetworks/{name}",
                'secondary_ranges': ranges,
            }
            # Filter down to specific regions, if desired
            if regions:
                subnets = [subnet for subnet in subnets if subnet['region'] in regions]
            subnets.append(subnet)
        return subnets
    except Exception as e:
        raise e


async def get_gke_clusters(project_id: str, access_token: str) -> list:

    gke_clusters = []

    try:
        url = f"https://container.googleapis.com/v1/projects/{project_id}/locations/-/clusters"
        data = await get_api_data(url, access_token)
        #print(data)
        for item in data:
            region = "unknown"
            if location := item.get('location'):
                region = location[0:-2] if location[-2:-1] == "-" else location
            network = "N/A"
            network_project_id = project_id
            subnet = "N/A"
            master_range = "N/A"
            if network_config := item.get('networkConfig'):
                network = network_config.get('network', 'UNKNOWN')
                network_project_id = network.split('/')[-4]
                subnet = network_config.get('subnetwork', 'UNKNOWN')
            if private_cluster_config := item.get('privateClusterConfig'):
                master_range = private_cluster_config.get('masterIpv4CidrBlock')
            gke_cluster = {
                'name': item['name'],
                'region': region,
                'network': network,
                'network_project_id': network_project_id,
                'subnet': subnet,
                'master_range': master_range,
                'current_master_version': item.get('currentMasterVersion', 'UNKNOWN'),
                'current_node_version': item.get('currentNodeVersion', "UNKNOWN"),
            }
            if ip_allocation_policy := item.get('ipAllocationPolicy'):
                gke_cluster.update({
                    'pods_range': ip_allocation_policy.get('clusterSecondaryRangeName'),
                    'pods_cidr': ip_allocation_policy.get('clusterIpv4Cidr'),
                    'services_range': ip_allocation_policy.get('servicesSecondaryRangeName'),
                    'services_cidr': ip_allocation_policy.get('servicesIpv4Cidr'),
                })
            else:
                gke_cluster.update({k: "N/A" for k in ('pods_cidr', 'pods_range', 'services_cidr', 'services_range')})
            gke_clusters.append(gke_cluster)
        return gke_clusters

    except Exception as e:
        return []


async def main():

    splits = {'start': time()}

    settings = await get_settings()
    if host_project_id := settings.get('host_project_id'):
        quota_project_id = settings.get('quota_project_id', host_project_id)
    else:
        quit("'host_project_id' not defined in YAML file!")
    if json_key := settings.get('json_key'):
        access_token = await read_service_account_key(json_key)
    else:
        access_token = await get_adc_token(quota_project_id=quota_project_id)

    splits.update({'get_token': time()})

    projects = await get_projects(access_token=access_token)
    splits.update({'get_projects': time()})

    _ = await get_shared_vpc_service_projects(host_project_id=host_project_id, access_token=access_token)
    # Filter complete projects list down to ones that are Shared VPC service projects
    projects = [project for project in projects if project['id'] in _]
    splits.update({'get_service_projects': time()})


    #print(projects)
    networks = await get_networks(project_id=host_project_id, access_token=access_token)
    splits.update({'get_networks': time()})

    #print(vpc_networks)

    _subnets = await get_subnets(project_id=host_project_id, access_token=access_token)
    splits.update({'get_subnets': time()})

    # Match each subnet to a network
    subnets = []
    for subnet in _subnets:
        for network in networks:
            for s in network['subnets']:
                if s['id'] == subnet['id']:
                    subnet.update({'network': network['name']})
                    break
        subnets.append(subnet)
    splits.update({'match_subnets_to_networks': time()})

    #print(subnets)
    tasks = [get_gke_clusters(project['id'], access_token) for project in projects]
    _gke_clusters = await gather(*tasks)

    gke_clusters = []
    for _ in _gke_clusters:
        if isinstance(_, dict):
            gke_clusters.append(_)
        if isinstance(_, list):
            for gke_cluster in _:
                gke_clusters.append(gke_cluster)
        #print(_)
    #gke_clusters = [_ for _ in results if _ != []]
    splits.update({'get_gke_clusters': time()})

    # Populate subnet secondary ranges with GKE services
    for gke_cluster in gke_clusters:
        for subnet in subnets:
            if gke_cluster['subnet'] == subnet['id']:
                for i, r in enumerate(subnet['secondary_ranges']):
                    if r['name'] == gke_cluster['services_range']:
                        subnet['secondary_ranges'][i].update({
                            'gke_cluster': gke_cluster['name'],
                            'master_range': gke_cluster['master_range'],
                        })
                subnets = [subnet if _['id'] == subnet['id'] else _ for _ in subnets]
                break
    splits.update({'match_clusters_to_ranges': time()})

    start = splits.pop('start')
    last_split = start
    for key, timestamp in splits.items():
        duration = round((splits[key] - last_split), 3)
        splits.update({key: f"{duration:.3f}"})
        last_split = timestamp
    splits.update({'total': f"{round(last_split - start, 3):.3f}"})

    return {
        'projects': projects,
        'networks': networks,
        'subnets': subnets,
        'gke_clusters': gke_clusters,
        'splits': splits,
    }


if __name__ == "__main__":

    _ = run(main())
    pprint(_['gke_clusters'])
