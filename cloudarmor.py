#!/usr/bin/env python3

from asyncio import run, gather
from utils import get_adc_token, get_projects
from gcp_operations import make_api_call
from main import SecurityPolicy
from os import environ


async def main():

    try:
        access_token = await get_adc_token()
        if project_id := environ.get('PROJECT_ID'):
            project_ids = [project_id]
        else:
            projects = await get_projects(access_token)
            project_ids = [project.id for project in projects]
    except Exception as e:
        quit(e)

    policies = []
    try:
        urls = [f"/compute/v1/projects/{_}/global/securityPolicies" for _ in project_ids]
        tasks = [make_api_call(url, access_token) for url in urls]
        results = await gather(*tasks)
        #print(result)
        for item in results:
            _ = SecurityPolicy(item)
            print(_)
            policies.append(_)
            #print(item.get('name'), item.get('selfLink'))
    except Exception as e:
        raise e

if __name__ == "__main__":

    _ = run(main())
    print(_)
