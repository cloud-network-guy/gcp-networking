import asyncio
import os
import pathlib
import yaml
import json
import google.oauth2
import google.auth
import google.auth.transport.requests
from aiohttp import ClientSession

INPUT_FILE = 'commercial.yaml'
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
PWD = os.path.realpath(os.path.dirname(__file__))
SERVICE_USAGE_PARENTS = {'org_id': "organisations", 'folder_id': "folders", 'project_id': "projects"}


async def get_parameters(input_file: str) -> dict:

    _ = pathlib.Path(os.path.join(PWD, input_file))
    assert _.is_file() and _.stat().st_size > 0,  f"File '{input_file}' does not exist or is empty!"
    with open(_, mode="rb") as fp:
        return yaml.load(fp, Loader=yaml.FullLoader)


async def get_access_token(key_file: str = None, quota_project_id: str = None) -> str:
    """
    Authenticate to GCP and return an access token
    """
    if key_file:
        # Convert relative to full path
        key_file = os.path.join(PWD, key_file)
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    else:
        # Authenticate via ADC
        credentials, project_id = google.auth.default(scopes=SCOPES, quota_project_id=quota_project_id)
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
                if len(url.split('/compute/v1/projects/')[-1].split('/')) == 3:
                    items_key = "items"
            else:
                items_key = "resources"
        else:
            items_key = url.split('/')[-1]
    headers = {'Authorization': f"Bearer {access_token}"}
    params = {} if not params else params
    data = []
    try:
        while True:
            #print(url, params, items_key)
            async with (session.get(url, headers=headers, params=params) as response):
                #print(response)
                if int(response.status) == 200:
                    json_data = await response.json()
                    if 'aggregated/' in url:
                        for k, v in json_data.get(items_key, {}).items():
                            if _ := v.get(url.split("/")[-1]):
                                data.extend(_)
                    else:
                        if items_key:
                            _ = json_data.get(items_key, [])
                            data.extend(_)
                        else:
                            data = [json_data]
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
    _ = await get_api_data(session, url, access_token, qs)
    await session.close()
    for project in _:
        projects.append({
            'name': project.get('name'),
            'id': project.get('projectId'),
            'number': project.get('projectNumber'),
            'state': project.get('lifecycleState'),
            'labels': project.get('labels'),
        })
    if state:
        projects = [p for p in projects if p['state'] == state.upper()]
    return projects


async def get_service_projects(project_id: str, access_token: str) -> list:
    """
    Given a Shared VPC host project, get list of all projects under that folder
    """
    session = ClientSession(raise_for_status=False)
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/getXpnResources"
    _ = await get_api_data(session, url, access_token)
    await session.close()
    assert len(_) > 0, f"No service projects found in Project ID '{project_id}'"
    return [p['id'] for p in _]


async def get_service_usage(parent: dict, access_token: str) -> list:
    """
    Get Service Usage of an org, folder, or project
    """
    p = None
    for k, v in SERVICE_USAGE_PARENTS.items():
        if _ := parent.get(k):
            p = f"{v}/{_}"
            break
    assert p, f"parent must be one of these keys: {SERVICE_USAGE_PARENTS.keys()}"
    session = ClientSession(raise_for_status=True)
    url = f"https://serviceusage.googleapis.com/v1/{p}/services"
    #print(url)
    _ = await get_api_data(session, url, access_token)
    #print(_)


async def get_subnetworks(project_id: str, network: str, access_token: str, region: str = None) -> list:
    """
    Given a Shared VPC host project and VPC network name, return all private subnets for a given region
    """
    session = ClientSession(raise_for_status=False)

    # Get network details, which includes list of its subnetworks
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/networks/{network}"
    _networks = await get_api_data(session, url, access_token)
    networks = [n for n in _networks if n['name'] == network]
    _network = await get_api_data(session, url, access_token)
    assert len(_network) > 0 and _network[0].get('name') == network, f"VPC network '{network}' not found in project '{project_id}'"

    subnets_list = [subnetwork for subnetwork in networks[0].get('subnetworks', [])]
    #print(subnets_list)
    #return []

    # Get all subnetworks that are in the subnetworks list from above
    if region:
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/subnetworks"
    else:
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/aggregated/subnetworks"
    #print(url)
    _subnetworks = await get_api_data(session, url, access_token)
    #print(len(_subnetworks[0]))
    #print("got back", len(_), "from url", url)

    subnetworks = []
    #return subnetworks
    for s in _subnetworks:
        self_link = s['selfLink']
        #print(self_link, [_ for _ in _subnetworks if _ == self_link], subnetwork['purpose'])
        if self_link in subnets_list and s['purpose'] == 'PRIVATE':
        #if s['purpose'] == 'PRIVATE':
            #print("Found subnet:", self_link)
            subnetworks.append({
                'name': s['name'],
                'id': self_link.replace('https://www.googleapis.com/compute/v1/', ''),
                'region': s['region'].split('/')[-1],
                'project_id': project_id,
                #'members': [],
                'attached_projects': None,
                'cidr_range': s['ipCidrRange'],
            })
    await session.close()
    return subnetworks


async def get_subnet_iam_binding(subnet_id: str, access_token: str) -> list:

    session = ClientSession(raise_for_status=True)
    url = f"https://compute.googleapis.com/compute/v1/{subnet_id}/getIamPolicy"
    #print(url)
    qs = {'optionsRequestedPolicyVersion': 1}
    _ = await get_api_data(session, url, access_token, qs, "bindings")
    members = []
    for binding in _:
        if binding.get('role') == "roles/compute.networkUser":
            members.extend(binding.get('members', []))
    await session.close()
    return members


async def get_instances(session: ClientSession, project_id: str, access_token :str) -> list:

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/aggregated/instances"
    _ = await get_api_data(session, url, access_token)
    #print(_)
    instances = []
    for i in _:
        for nic in i.get('networkInterfaces', []):
            if network := nic.get('network'):
                network_name = network.split("/")[-1]
                host_project_id = network.split("/")[-4]
            subnet_id = None
            if subnetwork := nic.get('subnetwork'):
                subnet_id = subnetwork.replace('https://www.googleapis.com/compute/v1/', '')
                region = subnetwork.split('/')[-3]
            instances.append({
                'name': i.get('name'),
                'nic': nic.get('name'),
                'project_id': project_id,
                'host_project_id': host_project_id,
                'network': network_name,
                'subnetwork': subnet_id,
            })
    #await session.close()
    return instances


async def main():

    parameters = await get_parameters(INPUT_FILE)

    host_project_id = parameters.get('host_project_id')
    network = parameters.get('network', "default")
    region = parameters.get('region')

    try:
        access_token = await get_access_token(parameters.get('key_file'))
    except Exception as e:
        quit(e)

    projects_filter = None
    for k in SERVICE_USAGE_PARENTS.keys():
        if v := parameters.get(k):
            projects_filter = f"parent.id={v}"
    _ = await get_projects(access_token, projects_filter, state='ACTIVE')
    projects = {p['id']: p for p in _}
    #quit()

    service_projects = await get_service_projects(host_project_id, access_token)
    print(f"Found {len(service_projects)} Service Projects using Shared VPC Host Project '{host_project_id}'")
    service_projects = [p for p in service_projects if projects.get(p)]
    #service_projects = service_projects[200:]
    print(f"Found {len(service_projects)} Service Projects after filtering")

    session = ClientSession(raise_for_status=True)
    tasks = [get_instances(session, p, access_token) for p in service_projects]
    _ = await asyncio.gather(*tasks)
    await session.close()
    instances = []
    for data in _:
        instances.extend(data)
    #instances = dict(zip(service_projects, _))
    #instances = _
    instances = [i for i in instances if i['network'] == network]
    used_subnetworks = set([i['subnetwork'] for i in instances])
    #print(instances)
    #quit()

    _ = await get_subnetworks(host_project_id, network, access_token, region=region)
    #print([i['subnetwork'] for i in instances])
    subnetworks = {s['id']: s for s in _ if s['id'] in used_subnetworks}

    #subnetworks = {s['id']: s for s in _ if 'subnet1' in s['name']}
    #region = 'northamerica-northeast1'
    #if region:
    #    subnetworks = {s: subnetwork for s, subnetwork in subnetworks.items() if subnetwork['region'] == region}
    #print(f"Found {len(subnetworks)} Subnetworks in Shared VPC Host Project '{host_project_id}'")
    #print(subnetworks)
    #quit()




    matches = {s: [] for s in subnetworks.keys()}
    for s, subnetwork in subnetworks.items():
        #print(s)
        attached_projects = set([i['project_id'] for i in instances if i['subnetwork'] == s])
        if len(attached_projects) > 0:
            matches[s].extend(attached_projects)
            #print(s.split('/')[-1], "attached_projects =", [f"{p}" for p in attached_projects])
    #print("found", len(matches.values) if , "matches!")
    _ = {k: v for k, v in matches.items() if len(v) > 0}

    subnetwork_ids = list(subnetworks.keys())
    tasks = [get_subnet_iam_binding(s, access_token) for s in subnetwork_ids]
    _ = await asyncio.gather(*tasks)
    subnetwork_members = dict(zip(subnetwork_ids, _))

    for k,v in matches.items():
        for ap in v:
            p = projects[ap]
            sa = f"serviceAccount:{p.get('number')}-compute@developer.gserviceaccount.com"
            if sa not in subnetwork_members[k]:
                print(f"Project {ap} is missing permissions on subnet {k}")

    return matches

if __name__ == "__main__":

    from pprint import pprint

    try:
        _ = asyncio.run(main())
        #pprint(_)
    except Exception as e:
        raise e

