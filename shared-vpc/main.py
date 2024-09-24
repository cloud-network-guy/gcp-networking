import asyncio
import sys
import os
import pathlib
import tomli
import ipaddress
import collections
import google.oauth2
import google.auth
import google.auth.transport.requests
from aiohttp import ClientSession

INPUT_FILE = 'profiles.toml'
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
PWD = os.path.realpath(os.path.dirname(__file__))


async def get_profiles(input_file: str = INPUT_FILE) -> dict:

    _ = pathlib.Path(os.path.join(PWD, input_file))
    assert _.is_file() and _.stat().st_size > 0,  f"File '{input_file}' does not exist or is empty!"
    with open(_, mode="rb") as fp:
        return tomli.load(fp)


async def get_profile(profile_name: str) -> dict:

    _profiles = await get_profiles()
    global_profile = _profiles.get('global', {})
    access_token = await get_access_token(global_profile.get('key_file')),
    _profile = {
        'host_project_id': global_profile.get('host_project_id'),
        'access_token': access_token,
    }
    _p = _profiles.get(profile_name)
    _profile.update({
       'network': _p.get('network', "default"),
       'region': _p.get('region', "us-central1"),
       'gke_master_range': _p.get('gke_master_range', "10.0.0.0/16"),
       'num_clusters':  3,
    })
    #print("profile:", _profile)
    return _profile


async def get_access_token(key_file: str = None) -> str:
    """
    Authenticate to GCP and return an access token
    """
    if key_file:
        # Convert relative to full path
        key_file = os.path.join(PWD, key_file)
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    else:
        # Authenticate via ADC
        credentials, project_id = google.auth.default(scopes=SCOPES, quota_project_id=None)
    # Generate access token
    _ = google.auth.transport.requests.Request()
    credentials.refresh(_)
    return credentials.token


async def get_api_data(session: ClientSession, url: str, access_token: str, params: dict = None, items_key: str = None) -> list:
    """
    Make a Rest API to GCP, return data
    """
    if not items_key:
        if 'compute.googleapis.com' in url:
            if '/zones' in url or '/regions' in url or '/global' in url or '/aggregate' in url:
                if 3 <= len(url.split('/compute/v1/projects/')[-1].split('/')) <= 4:
                    items_key = "items"
            else:
                items_key = "resources"
        else:
            items_key = url.split('/')[-1]
    headers = {'Authorization': f"Bearer {access_token}"}
    params = {} if not params else params
    data = []
    print(url, items_key)
    try:
        while True:
            async with (session.get(url, headers=headers, params=params) as response):
                if int(response.status) == 200:
                    json_data = await response.json()
                    print(url, items_key, json_data)
                    if 'aggregated/' in url:
                        for k, v in json_data.get(items_key, {}).items():
                            if _ := v.get(url.split("/")[-1]):
                                data.extend(_)
                    else:
                        if items_key:
                            _ = json_data.get(items_key, [])
                            data.extend(_)
                        else:
                            data = [json_data]  # API returned a dictionary
                    if next_page_token := json_data.get('nextPageToken'):
                        params.update({'pageToken': next_page_token})
                    else:
                        break
                else:
                    break
    except Exception as e:
        raise e

    return data


async def get_projects(access_token: str, parent_filter: str = None, state: str = None) -> list:
    """
    Get list of all projects
    """
    projects = []
    session = ClientSession(raise_for_status=False)
    url = "https://cloudresourcemanager.googleapis.com/v1/projects"
    qs = {'filter': parent_filter} if parent_filter else None
    _projects = await get_api_data(session, url, access_token, qs)
    await session.close()
    for p in _projects:
        projects.append({
            'name': p.get('name'),
            'id': p.get('projectId'),
            'number': p.get('projectNumber'),
            'state': p.get('lifecycleState'),
            'labels': p.get('labels'),
        })
    if state:
        projects = [p for p in _projects if p['state'] == state.upper()]
    return projects


async def get_service_projects(host_project_id: str, access_token: str) -> list:
    """
    Given a Shared VPC host project, get list of all projects under that folder
    """
    session = ClientSession(raise_for_status=False)
    url = f"https://compute.googleapis.com/compute/v1/projects/{host_project_id}/getXpnResources"
    _resources = await get_api_data(session, url, access_token)
    await session.close()
    assert len(_resources) > 0, f"No service projects found in Project ID '{host_project_id}'"
    return [r['id'] for r in _resources]


async def get_networks(project_id: str, access_token: str) -> list:
    """
    Given a Shared VPC host project and VPC network name, return all private subnets for a given region
    """
    session = ClientSession(raise_for_status=True)
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/networks"
    resources = await get_api_data(session, url, access_token)
    await session.close()
    assert len(resources) > 0, f"No VPC Networks found in Project ID '{project_id}'"
    networks = []
    for network in resources:
        subnetworks = network.get('subnetworks', [])
        subnet_regions = collections.Counter([s.split('/')[-3] for s in subnetworks])
        _ = {
            'project_id': project_id,
            'name': network['name'],
            'num_subnetworks': len(subnetworks),
            'subnet_regions': [r[0] for r in subnet_regions.most_common()],
        }
        networks.append(_)
    networks = sorted(networks, key=lambda n: n['num_subnetworks'], reverse=True)
    return networks


async def get_subnetworks(project_id: str, network: str, access_token: str, region: str = None) -> list:
    """
    Given a Shared VPC host project and VPC network name, return all private subnets for a given region
    """
    session = ClientSession(raise_for_status=True)

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/networks"
    _networks = await get_api_data(session, url, access_token)
    print("networks:", _networks)
    _networks = [n for n in _networks if n['name'] == network]
    _network = _networks[0]
    assert _network.get('name') == network, f"VPC network '{network}' not found in project '{project_id}'"
    subnets_list = [subnetwork for subnetwork in _network.get('subnetworks', [])]

    # Get all subnetworks that are in the subnetworks list from above
    #url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/subnetworks"
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/aggregated/subnetworks"
    _subnetworks = await get_api_data(session, url, access_token)
    print(_subnetworks)
    subnetworks = []
    for subnetwork in _subnetworks:
        self_link = subnetwork['selfLink']
        if self_link in subnets_list and subnetwork['purpose'] == 'PRIVATE':
            subnetworks.append({
                'name': subnetwork['name'],
                'id': self_link.replace('https://www.googleapis.com/compute/v1/', ''),
                'region': subnetwork['region'].split('/')[-1],
                'project_id': project_id,
                'main_ip_range': subnetwork['ipCidrRange'],
                'secondary_ranges': [_['rangeName'] for _ in subnetwork.get('secondaryIpRanges', [])],
            })
    await session.close()
    print(_subnetworks)
    return subnetworks


async def get_subnet_iam_bindings(subnet_id: str, access_token: str) -> list:

    session = ClientSession(raise_for_status=True)
    url = f"https://compute.googleapis.com/compute/v1/{subnet_id}/getIamPolicy"
    query_string = {'optionsRequestedPolicyVersion': 1}
    _ = await get_api_data(session, url, access_token, query_string, "bindings")
    members = []
    for binding in _:
        if binding.get('role') == "roles/compute.networkUser":
            members.extend(binding.get('members', []))
    await session.close()
    return members


async def get_gke_clusters(project_id: str, access_token: str, session: ClientSession = None) -> list:
    """
    Given a Project ID, return network information for all GKE clusters
    """
    if not session:
        session = ClientSession(raise_for_status=False)
    url = f"https://container.googleapis.com/v1/projects/{project_id}/locations/-/clusters"
    try:
        _ = await get_api_data(session, url, access_token)
        #print(_)
        clusters = []
        for cluster in _.get('clusters', []):
            region = "unknown"
            if location := cluster.get('location'):
                region = location[0:-2] if location[-2:-1] == "-" else location
            master_range = "N/A"
            host_project_id = project_id
            network_name = "unknown"
            if network_config := cluster.get('networkConfig'):
                if network := network_config.get('network'):
                    network_name = network.split('/')[-1]
                    host_project_id = network.split('/')[-4]
            if private_cluster_config := cluster.get('privateClusterConfig'):
                master_range = private_cluster_config.get('masterIpv4CidrBlock')
            services_range_name = "unknown"
            if ip_allocation_policy := cluster.get('ipAllocationPolicy'):
                services_range_name = ip_allocation_policy.get('servicesSecondaryRangeName')
            clusters.append({
                'id': f"{project_id}/{region}/{cluster['name']}",
                'name': cluster['name'],
                'region': region,
                'project_id': project_id,
                'host_project_id': host_project_id,
                'network': network_name,
                'subnetwork': network_config.get('subnetwork'),
                'master_range': master_range,
                'services_range_name': services_range_name,
            })
        return clusters
    except AssertionError:
        return []


async def main(profile: str):


    profiles = await get_profiles(INPUT_FILE)
    global_profile = profiles.get('global', {})
    host_project_id = global_profile.get('host_project_id')
    access_token = await get_access_token(global_profile.get('key_file'))
    my_profile = profiles.get(profile)
    network = my_profile.get('network', "default")
    region = my_profile.get('region', "us-central1")
    gke_master_range = my_profile.get('gke_master_range', "10.0.0.0/16")
    num_clusters = 3

    # Get Shared VPC Service Projects
    service_projects = await get_service_projects(host_project_id, access_token)
    print(f"Found {len(service_projects)} Service Projects using Shared VPC Host Project '{host_project_id}'")

    # Get Subnetworks list from Host Network Project
    _ = await get_subnetworks(host_project_id, network, access_token, region=region)
    # Create a dictionary with subnet ID (projects/xxx/regions/yyy/subnetworks/zzzz) as key
    subnets = {subnet['id']: subnet for subnet in _}
    assert len(subnets) > 0, f"No subnets found in region '{region}' in network '{network}'"
    print(f"Found {len(subnets.keys())} Subnetworks in network '{network}'")

    # Get GKE Clusters from Service Projects
    session = ClientSession(raise_for_status=False)
    tasks = [get_gke_clusters(p, access_token, session) for p in service_projects]
    _ = await asyncio.gather(*tasks)
    await session.close()
    gke_clusters = [item for items in _ for item in items]  # Flatten list
    # Filter down to matching VPC Network
    gke_clusters = [_ for _ in gke_clusters if _['host_project_id'] == host_project_id and _['network'] == network]
    print(f"Found {len(gke_clusters)} GKE Clusters using network '{network}'")

    # Initialize a dictionary of all services ranges with subnet ID as key
    services_ranges = {}
    for subnet_id, subnet in subnets.items():
        secondary_ranges = sorted(subnet['secondary_ranges'], key=lambda x: x)  # Sort by range Name
        services_ranges.update({subnet_id: {_: None for _ in secondary_ranges if 'gke-services' in _}})

    # Populate subnet ranges with the allocated GKE Cluster name
    for gke_cluster in gke_clusters:
        services_range = gke_cluster['services_range_name']
        subnet_id = gke_cluster['subnetwork']
        subnet_ranges = services_ranges.get(subnet_id, {})
        if services_range in subnet_ranges.keys():
            subnet_ranges.update({services_range: gke_cluster['id']})
        services_ranges.update({subnet_id: subnet_ranges})

    # Check each subnet for free services ranges
    subnet_id = None
    first_free_range = None
    for subnet_id, services_ranges in services_ranges.items():
        unused_ranges = [k for k, v in services_ranges.items() if not v]
        if len(unused_ranges) >= num_clusters:
            # Found a subnet with enough unused ranges
            first_free_range = unused_ranges[0]
            break

    subnet = subnets[subnet_id]
    assert subnet['region'] == region, f"Selected subnet '{subnet_id}' is not in region '{region}'"
    assert subnet['project_id'] == host_project_id, f"Selected subnet '{subnet_id}' is not in project '{host_project_id}'"

    used_master_ranges = {_['master_range']: _['id'] for _ in gke_clusters}
    _ = list(ipaddress.ip_network(gke_master_range).subnets(new_prefix=28))
    for gke_master_range in _:
        if not used_master_ranges.get(gke_master_range):
            break

    output = {
        'subnet_id': subnet_id,
        'subnet_name': subnet['name'],
        'subnet_region': subnet['region'],
        'subnet_project': subnet_id.split('/')[-5],
        'main_ip_range': subnet['main_ip_range'],
        'num_free_ranges': len(unused_ranges),
        'network': network,
        'ip_range_services': first_free_range,
        'gke_master_range': str(gke_master_range),
        'access_type': "public",
        #'used_master_ranges': used_master_ranges,
    }
    [print(f"{k} = \"{v}\"") for k, v in output.items()]
    return output


if __name__ == "__main__":

    if not (profile := os.environ.get('PROFILE')):
        if len(sys.argv) == 2:
            profile = sys.argv[1]
        else:
            quit(f"Usage: {sys.argv[0]} <PROFILE_NAME>")

    try:
        _ = asyncio.run(main(profile))
    except Exception as e:
        raise e
