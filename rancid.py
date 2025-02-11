#!/usr/bin/env python3 

import yaml
from time import time
from gcloud.aio.storage import Storage
from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, get_calls, write_file, write_data_file
from gcp_utils import get_access_token, get_projects, get_api_data, get_project_from_account_key
#from gcp_classes import Instance, ForwardingRule, CloudRouter, GKECluster


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    key_dir = settings.get('key_dir', './')
    if environments := settings.get('environments'):
        projects = {}
        for environment_key, env_settings in environments.items():
            if auth_files := env_settings.get('auth_files'):
                for auth_file in auth_files:
                    key_file = f"{key_dir}/{auth_file}"
                    #sa_key = await read_service_account_key(key_file)
                    #project_id = sa_key.get('project_id')
                    project_id = await get_project_from_account_key(key_file)
                    access_token = await get_access_token(settings.get('key_file'))
                    projects.update({
                        project_id: {
                            'environment_key': environment_key,
                            'key_file': key_file,
                            'access_token': access_token,
                            'bucket_name': env_settings.get('bucket_name'),
                            'bucket_prefix': env_settings.get('bucket_prefix', ""),
                        }
                    })
            else:
                projects = []
    else:
        try:
            # Try to Authenticate via ADCs
            access_token = await get_access_token()
            projects = await get_projects(access_token)
            projects = {project.id: {'access_token': access_token} for project in projects}   # Use same token for all projects
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
    session = ClientSession(raise_for_status=False)
    for project in projects.values():
        access_token = project.get('access_token')
        _ = project.get('urls', [])
        #tasks.extend([make_api_call(url, access_token) for url in _])
        tasks.extend([get_api_data(session, url, access_token) for url in _])
        urls.extend(_)

    # Make the API calls
    raw_data = await gather(*tasks)
    await session.close()

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
            #tasks.append(write_data_file(file_name, data))
            tasks.append(write_data_file(file_name, data))
    await gather(*tasks)

    #print({k: v.get('bucket_name') for k, v in projects.items()})

    # Write to bucket
    start = time()
    buckets = {k: (v.get('bucket_name'), v.get('bucket_prefix'), v.get('key_file')) for k, v in projects.items() if v.get('bucket_name')}
    #print(buckets)
    for project_id, bucket in buckets.items():
        try:
            bucket_name = bucket[0]
            bucket_prefix = bucket[1]
            service_file = bucket[2]
            async with Storage(service_file=service_file) as storage:
                storage_objects = {f'{project_id}/{k}.{file_format}': projects[project_id]['data'][k] for k in calls.keys()}
                if bucket_prefix:
                    bucket_prefix.replace('/', "")
                    storage_objects.update({f'{bucket_prefix}/{k}': v for k, v in storage_objects.items()})
                tasks = [storage.upload(
                    bucket=bucket_name,
                    object_name=k,
                    file_data=yaml.dump(v),
                    content_type="text/yaml",
                ) for k, v in storage_objects.items()]
                await gather(*tasks)
        except Exception as e:
            await storage.close()
            raise RuntimeError(e)
    print("writing to bucket took", round(time() - start, 3), "seconds")

    return {k: v.get('data') for k, v in projects.items()}


if __name__ == "__main__":

    _ = run(main())

