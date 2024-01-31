#!/usr/bin/env python3 

from asyncio import run, gather
from utils import get_adc_token, read_service_account_key, write_data_file, get_settings, get_calls
from gcp_operations import get_project_ids, make_gcp_call


async def main():

    try:
        settings = await get_settings()
    except Exception as e:
        quit(e)

    key_dir = settings.get('key_dir', './')
    if environments := settings.get('environments'):
        projects = {}
        for environment, env_settings in environments.items():
            if auth_files := env_settings.get('auth_files'):
                for auth_file in auth_files:
                    key_file = f"{key_dir}/{auth_file}"
                    sa_key = await read_service_account_key(key_file)
                    project_id = sa_key.get('project_id')
                    projects.update({project_id: {
                        'environment': environment,
                        'access_token': sa_key.get('access_token'),
                    }})
            else:
                projects = []
    else:
        try:
            # Try to Authenticate via ADCs
            access_token = await get_adc_token()
            project_ids = await get_project_ids(access_token)
            projects = {_: {'access_token': access_token} for _ in project_ids}   # Use same token for all projects
        except Exception as e:
            quit(e)

    calls = await get_calls()

    # Generate the URls for each Project
    for project_id, project in projects.items():
        urls = []
        for k, v in calls.items():
            for call in v.get('calls', []):
                urls.append(f"/compute/v1/projects/{project_id}/{call}")
        project['urls'] = urls
        projects.update({project_id: project})

    tasks = []
    urls = []
    for project in projects.values():
        access_token = project.get('access_token')
        _ = project.get('urls', [])
        tasks.extend([make_gcp_call(url, access_token, api_name='compute') for url in _])
        urls.extend(_)

    # Make the API calls
    raw_data = await gather(*tasks)
    data_by_url = dict(zip(urls, raw_data))
    del raw_data

    # Organize the raw data by project
    for project_id, project in projects.items():
        project['data'] = {}
        for k, v in calls.items():
            _ = f'{project_id}/{k}'
            urls = [f"/compute/v1/projects/{project_id}/{call}" for call in v.get('calls', [])]
            data = []
            for url in urls:
                data.extend(data_by_url[url])
            project['data'][k] = data
        projects.update({project_id: project})

    # Write to local disk
    file_format = settings.get('file_format', 'yaml')
    tasks = []
    for project_id, project in projects.items():
        for k in calls.keys():
            file_name = f'{project_id}/{k}.{file_format}'
            data = project['data'][k]
            tasks.append(write_data_file(file_name, data))
    await gather(*tasks)

    return {k: v.get('data') for k, v in projects.items()}

if __name__ == "__main__":

    _ = run(main())
    print(_)

