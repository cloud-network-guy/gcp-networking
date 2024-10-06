import os
import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
from aiohttp import ClientSession

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
PWD = os.path.realpath(os.path.dirname(__file__))


async def get_access_token(key_file: str = None, quota_project_id: str = None) -> str:
    """
    Authenticate to GCP and return an access token
    """
    if key_file:
        # Convert relative to full path
        key_file = os.path.join(PWD, key_file)
        credentials = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
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
    api_name = None
    if url.startswith('http:') or url.startswith('https:'):
        # Urls is fully defined, just need to find API name
        _ = url[7:] if url.startswith('http:') else url[8:]
        api_name = _.split('.')[0]

    # Url is something like /compute/v1/projects/{PROJECT_ID}...
    url = url[1:] if url.startswith("/") else url
    if not api_name:
        if 'clusters' in url:
            api_name = "container"
        else:
            api_name = url.split('/')[0]
        url = f"https://{api_name}.googleapis.com/{url}"

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
    #print(url, items_key)
    try:
        while True:
            async with (session.get(url, headers=headers, params=params) as response):
                if int(response.status) == 200:
                    json_data = await response.json()
                    #print(url, items_key, json_data)
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


async def get_projects(access_token: str, parent_filter: str = None, state: str = None, sort_by: str = None) -> list:
    """
    Get list of all projects
    """
    from gcp_classes import GCPProject

    session = ClientSession(raise_for_status=False)
    url = "https://cloudresourcemanager.googleapis.com/v1/projects"
    qs = {'filter': parent_filter} if parent_filter else None
    _projects = await get_api_data(session, url, access_token, qs)
    await session.close()

    projects = [GCPProject(p) for p in _projects]
    if state:
        projects = [p for p in projects if p.state == state.upper()]
    sort_by = sort_by.lower() if sort_by else None
    if sort_by in ('name', 'id', 'number', 'creation', 'create_timestamp'):
        projects = sorted(list(projects), key=lambda x: getattr(x, sort_by), reverse=False)
    return projects


async def get_project(project_id: str, access_token: str, parent_filter: str = None) -> dict:
    """
    Get details of a specific project
    """
    from gcp_classes import GCPProject

    try:
        session = ClientSession(raise_for_status=False)
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}"
        qs = {'filter': parent_filter} if parent_filter else None
        _project = await get_api_data(session, url, access_token, qs)
        await session.close()
        project = GCPProject(_project[0])
        return project.__dict__
    except Exception as e:
        raise e


async def get_service_projects(host_project_id: str, access_token: str) -> list:
    """
    Given a Shared VPC host project, get list of all projects under that folder
    """
    session = ClientSession(raise_for_status=False)
    url = f"https://compute.googleapis.com/compute/v1/projects/{host_project_id}/getXpnResources"
    _resources = await get_api_data(session, url, access_token)
    await session.close()
    assert len(_resources) > 0, f"No service projects found in Project ID '{host_project_id}'"
    return [r['id'] for r in _resources if r.get('type') == "PROJECT"]


async def get_networks(project_id: str, access_token: str) -> list:
    """
    Given a Shared VPC host project and VPC network name, return all private subnets for a given region
    """
    from gcp_classes import Network

    session = ClientSession(raise_for_status=True)
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/networks"
    _resources = await get_api_data(session, url, access_token)
    await session.close()
    assert len(_resources) > 0, f"No VPC Networks found in Project ID '{project_id}'"
    networks = []
    for _network in _resources:
        network = Network(_network)
        #subnet_regions = collections.Counter([s.split('/')[-3] for s in subnetworks])
        networks.append(network)
    #networks = sorted(networks, key=lambda n: n['num_subnetworks'], reverse=True)
    return networks


async def get_project_from_account_key(key_file: str) -> dict:
    from file_utils import read_data_file

    _ = await read_data_file(key_file, "json")
    return _.get('project_id')


