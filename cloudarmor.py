#!/usr/bin/env python3

from pprint import pprint
from os import environ
from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import SecurityPolicy


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    if project_id := environ.get('PROJECT_ID'):
        project_ids = [project_id]
    else:
        projects = await get_projects(access_token)
        project_ids = [project.id for project in projects]

    policies = []
    session = ClientSession(raise_for_status=False)
    try:
        urls = [f"/compute/v1/projects/{pid}/global/securityPolicies" for pid in project_ids]
        #tasks = [make_api_call(url, access_token) for url in urls]
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results = await gather(*tasks)
        results = [item for items in results for item in items]  # Flatten results
        for item in results:
            _ = SecurityPolicy(item)
            policies.append(_)
            #print(item.get('name'), item.get('selfLink'))
    except Exception as e:
        raise e
    await session.close()
    return policies


if __name__ == "__main__":

    _ = run(main())
    _ = [policy for policy in _ if policy.name == 'lbl-dev-whitelist']
    for policy in _:
        rules = sorted(list(policy.rules), key=lambda x: int(x.get('priority')), reverse=False)
        for rule in rules:
            print("{")
            for field in ('priority', 'description', 'action'):
                if isinstance(rule.get(field), int):
                    print(f"  {field} = {rule.get(field)}")
                else:
                    print(f"  {field} = \"{rule.get(field)}\"")
            if rule['match'].get("versionedExpr") == "SRC_IPS_V1":
                print(f"  ip_ranges = {rule['match']['config']['srcIpRanges']}")
            else:
                print(f"  expr = \"{rule['match']['expr']['expression']}\"")
            print("},")
