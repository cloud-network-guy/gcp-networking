#!/usr/bin/env python3

from asyncio import run, gather
from gcp_operations import get_projects, make_api_call, parse_project, get_api_data
from utils import get_adc_token, get_settings
from aiohttp import ClientSession


async def main():

    try:
        settings = await get_settings()
        access_token = await get_adc_token(quota_project_id=settings.get('quota_project_id'))
    except Exception as e:
        quit(e)


    #projects = await get_projects(access_token, sort_by='created')
    #if len(projects) < 1:
    #    quit("Didn't find any projects")

    async with ClientSession(raise_for_status=True) as session:
        url = 'https://cloudresourcemanager.googleapis.com/v1/projects'
        projects = await make_api_call(url, access_token, session)

        #    print(type(results))
        #    projects = results
        #return projects
        #quit()
        #results = [item async for item in async_generator()]

        #_ = await make_api_call('https://cloudresourcemanager.googleapis.com/v1/projects', access_token, session)
        #if sort_by in PROJECT_FIELDS.values():
        #    # Sort by a field defined in the API
        #    _ = sorted(list(_), key=lambda x: x.get(sort_by), reverse=False)
        #return tuple(_)

        #tasks = (parse_project(project) for project in projects)
        #projects = await gather(*tasks)

        #async for results in parse_project(project) for project in projects)
        #results = [project async for project in parse_project(projects)]

        #if sort_by in PROJECT_FIELDS.keys():
        #    # Sort by a field defined by us
        #    projects = sorted(list(projects), key=lambda x: x.get(sort_by), reverse=False)
        #projects = tuple(projects)

    #return projects

    #urls = (f"https://cloudresourcemanager.googleapis.com/v1/projects/{project['id']}" for project in projects)
    urls = (f"https://cloudresourcemanager.googleapis.com/v1/projects/{project['projectId']}" for project in projects)
    #return list(urls)

    async with ClientSession(raise_for_status=True) as session:
    #    results = [item async for item in get_api_data(urls, access_token, session)]

        async for results in get_api_data(urls, access_token, session):
            print(results)

        #tasks = (make_api_call(urls, access_token, session) for url in urls)
        #_ = await gather(*tasks)
        #projects = _

    #print(results)
    return results
    #tasks = (parse_project(project) for project in _)
    #projects = await gather(*tasks)
    return projects

    return projects

if __name__ == "__main__":

    _ = run(main())

    print(_)
    #print([project['id'] for project in _])
