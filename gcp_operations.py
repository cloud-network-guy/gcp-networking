from aiohttp import ClientSession
from asyncio import gather

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
VERIFY_SSL = True
PROJECT_FIELDS = {
    'name': "name",
    'id': "projectId",
    'number': "projectNumber",
    'created': "createTime",
    'status': "lifecycleState",
    'labels': "labels",
}


"""
async def make_gcp_call(call: str, access_token: str, api_name: str) -> dict:

    call = call[1:] if call.startswith("/") else call
    url = f"https://{api_name}.googleapis.com/{call}"
    if api_name in ['compute', 'sqladmin']:
        if 'aggregated' in call or 'global' in call:
            key = 'items'
        else:
            key = 'result'
    else:
        key = url.split("/")[-1]

    results = []
    call_id = None
    try:
        headers = {'Authorization': f"Bearer {access_token}"}
        params = {}
        async with ClientSession(raise_for_status=True) as session:
            while True:
                async with session.get(url, headers=headers, params=params) as response:
                    if int(response.status) == 200:
                        json_data = await response.json()
                        call_id = json_data.get('id')
                        if 'aggregated/' in url:
                            if key == 'items':
                                items = json_data.get(key, {})
                                for k, v in items.items():
                                    results.extend(v.get(url.split("/")[-1], []))
                        else:
                            if key == 'result':
                                items = json_data.get(key)
                                results.append(items)
                            else:
                                items = json_data.get(key, [])
                                results.extend(items)
                        if page_token := json_data.get('nextPageToken'):
                            params.update({'pageToken': page_token})
                        else:
                            break
                    else:
                        raise response
    except Exception as e:
        await session.close()

    return results
    


async def parse_project(project: dict) -> dict:

    _ = {k: project.get(v, "UNKNOWN") for k, v in PROJECT_FIELDS.items()}
    if parent := project.get('parent'):
        if folder := parent.get('folder'):
            _.update({'parent_folder_id': folder.get('id', "UNKNOWN")})
    return _


async def get_project_details(project_id: str, access_token: str) -> dict:

    try:
        url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
        _ = await make_api_call(url, access_token)
        _ = await parse_project(_[0]) if len(_) == 1 else {}
        return _
    except Exception as e:
        raise e


async def get_projects(access_token: str, sort_by: str = None) -> tuple:

    projects = []
    try:
        url = "https://cloudresourcemanager.googleapis.com/v1/projects"
        _ = await make_api_call(url, access_token)
        if sort_by in PROJECT_FIELDS.values():
            # Sort by a field defined in the API
            _ = sorted(list(_), key=lambda x: x.get(sort_by), reverse=False)
        tasks = (parse_project(project) for project in _)
        projects = await gather(*tasks)
        if sort_by in PROJECT_FIELDS.keys():
            # Sort by a field defined by us
            projects = sorted(list(projects), key=lambda x: x.get(sort_by), reverse=False)

    except Exception as e:
        raise e

    return tuple(projects)

async def get_project_ids(access_token: str, projects: list = None) -> tuple:

    try:
        projects = projects if projects else await get_projects(access_token)
        project_ids = [project['id'] for project in projects]
    except Exception as e:
        raise e

    return tuple(project_ids)
"""

"""
async def make_api_call(url: str, access_token: str, session: ClientSession = None) -> tuple:

    if url.startswith('http:') or url.startswith('https:'):
        # Urls is fully defined, just need to find API name
        _ = url[7:] if url.startswith('http:') else url[8:]
        api_name = _.split('.')[0]
    elif 'googleapis.com' in url:
        # Url is missing http/https at the beginning
        api_name = url.split('.')[0]
        url = f"https://{url}"
    elif '.' in url:
        raise f"Unhandled URL: {url}"
    else:
        # Url is something like /compute/v1/projects/{PROJECT_ID}...
        url = url[1:] if url.startswith("/") else url
        if 'clusters' in url:
            api_name = "container"
        else:
            api_name = url.split('/')[0]
        url = f"https://{api_name}.googleapis.com/{url}"

    if api_name in ['compute']:
        items_key = 'items' if 'aggregated' in url or 'global' in url else 'result'
    elif api_name in ['sqladmin']:
        items_key = 'items'
    else:
        items_key = url.split("/")[-1]

    results = []
    try:
        headers = {'Authorization': f"Bearer {access_token}"}
        params = {}  # Query string parameters to include in the request
        if not session:
            session = ClientSession(raise_for_status=True)
        while True:
            async with session.get(url, headers=headers, params=params, verify_ssl=VERIFY_SSL) as response:
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
                        results.extend(items)
                    else:
                        if json_data.get('name'):
                            results.append(json_data)
                    # Page token may be required if more than 500 results, else break
                    if next_page_token := json_data.get('nextPageToken'):
                        params.update({'pageToken': next_page_token})
                    else:
                        break
                else:
                    raise f"Invalid response: {str(response)}" #break  # non-200 usually means lack of permissions; just skip it
        await session.close()
    except Exception as e:
        await session.close()    # Something went wrong when opening the session; don't leave it hanging

    return tuple(results)


async def get_api_data(urls: list, access_token: str, session: ClientSession = None) -> tuple:

    headers = {'Authorization': f"Bearer {access_token}"}

    if not session:
        session = ClientSession(raise_for_status=True)

    for url in urls:
        #url = url[1:] if url.startswith("/") else url
        #api_name = url.split('/')[0]
        #url = f"https://{api_name}.googleapis.com/{url}"

        api_name = "compute"
        if url.startswith('http:') or url.startswith('https:'):
            # Urls is fully defined, just need to find API name
            _ = url[7:] if url.startswith('http:') else url[8:]
            api_name = _.split('.')[0]

        if api_name in ['compute', 'sqladmin']:
            items_key = 'items'
        else:
            items_key = url.split("/")[-1]
        #print(url)
        params = {}  # Query string parameters to include in the request
        try:
            results = []
            while True:
                #print(url)
                async with session.get(url, headers=headers, params=params, verify_ssl=VERIFY_SSL) as response:
                    #print(response)
                    if int(response.status) == 200:
                        json_data = await response.json()
                        if items := json_data.get(items_key):
                            if 'aggregated/' in url:
                                # With aggregated results, we have to walk each region to get the items
                                for k, v in items.items():
                                    _ = url.split("/")[-1]
                                    items = v.get(_, [])
                            #print(items)
                            results.extend(items)
                        else:
                            if json_data.get('name'):
                                #print(json_data)
                                results.append(json_data)
                        # If more than 500 results, use page token for next page and keep the party going
                        if next_page_token := json_data.get('nextPageToken'):
                            params.update({'pageToken': next_page_token})
                        else:
                            break
                    else:
                        break  # non-200 usually means lack of permissions; just skip it
        except Exception as e:
            await session.close()    # Something went wrong when opening the session; don't leave it hanging
            raise e

        session.close()
        yield tuple(results)

"""