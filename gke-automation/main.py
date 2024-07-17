#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from google.oauth2 import service_account
from pathlib import Path
from pprint import pprint
from platform import system
import google.auth
import google.auth.transport.requests
import google.oauth2
import yaml
import json

SETTINGS_FILE = "./settings.yaml"
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
        items_key = 'items' if 'aggregated' in url or 'global' in url else 'result'
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

    projects = []

    try:
        url = "https://cloudresourcemanager.googleapis.com/v1/projects"
        params = {'filter': "lifecycleState: ACTIVE"}
        data = await get_api_data(url, access_token, params)
        for item in data:
            _ = {
                'name': item.get('name'),
                'id': item.get('projectId'),
                'number': item.get('projectNumber'),
            }
            projects.append(_)
        return projects

    except Exception as e:
        raise e


async def get_vpc_networks(project_id: str, access_token: str) -> list:

    vpc_networks = []

    try:
        url = f"{COMPUTE_API_BASE}/projects/{project_id}/global/networks"
        data = await get_api_data(url, access_token)
        for item in data:
            _ = {k: item.get(k) for k in ('name', 'subnetworks')}
            vpc_networks.append(_)
        return vpc_networks

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
            _ = {k: item.get(k) for k in ('name', 'selfLink')}
            _.update({'region': item['region'].split("/")[-1]})
            _.update({
                'secondary_ranges': [rn['rangeName'] for rn in item.get('secondaryIpRanges', [])],
            })
            if regions:
                subnets = [subnet for subnet in subnets if subnet['region'] in regions]
            subnets.append(_)
        return subnets
    except Exception as e:
        raise e


async def get_gke_clusters(project_id: str, access_token: str) -> list:

    gke_clusters = []

    try:
        url = f"https://container.googleapis.com/v1/projects/{project_id}/locations/-/clusters"
        data = await get_api_data(url, access_token)
        print(data)
        for item in data:
            _ = {k: item.get(k) for k in ('name', 'currentMasterVersion', 'currentNodeVersion')}
            region = "unknown"
            if location := item.get('location'):
                region = location[0:-2] if location[-2:-1] == "-" else location
            master_range = "N/A"
            network_config = item.get('networkConfig')
            if private_cluster_config := item.get('privateClusterConfig'):
                master_range = private_cluster_config.get('masterIpv4CidrBlock')
            _.update({
                'region': region,
                'network': network_config.get('network'),
                'subnetwork': network_config.get('subnetwork'),
                'master_range': master_range,
            })
            if ip_allocation_policy := item.get('ipAllocationPolicy'):
                _.update({
                    'pods_ip_cidr': ip_allocation_policy.get('clusterIpv4Cidr'),
                    'pods_range_name': ip_allocation_policy.get('clusterSecondaryRangeName'),
                    'services_ip_cidr': ip_allocation_policy.get('servicesIpv4Cidr'),
                    'services_range_name': ip_allocation_policy.get('servicesSecondaryRangeName'),
                })
            gke_clusters.append(_)
        return gke_clusters

    except Exception as e:
        return []


async def main():

    settings = await get_settings()
    quota_project_id = settings.get('quota_project_id')
    if json_key := settings.get('json_key'):
        access_token = await read_service_account_key(json_key)
    else:
        access_token = await get_adc_token(quota_project_id=quota_project_id)

    projects = await get_projects(access_token=access_token)
    #projects = [{'id': "otl-ems-netops"}]
    host_project_id = settings.get('host_project_id', quota_project_id)
    vpc_networks = await get_vpc_networks(project_id=host_project_id, access_token=access_token)

    subnets = await get_subnets(project_id=host_project_id, access_token=access_token)
    print(subnets)
    tasks = [get_gke_clusters(project['id'], access_token) for project in projects]
    results = await gather(*tasks)
    gke_clusters = [_ for _ in results if _]
    return gke_clusters


if __name__ == "__main__":
    run(main())

