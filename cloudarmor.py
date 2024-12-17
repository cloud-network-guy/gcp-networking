#!/usr/bin/env python3

from os import environ
from asyncio import run, gather
from aiohttp import ClientSession
from itertools import chain
from file_utils import get_settings
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
        project_ids = [p.id for p in projects]

    policies = []
    session = ClientSession(raise_for_status=False)
    try:
        urls = [f"/compute/v1/projects/{p}/global/securityPolicies" for p in project_ids]
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results = await gather(*tasks)
        results = [item for item in list(chain(*results)) if item]
        for item in results:
            _ = SecurityPolicy(item)
            policies.append(_)
    except Exception as e:
        raise RuntimeError(e)
    await session.close()
    return policies


if __name__ == "__main__":

    _ = run(main())
    policy_name = environ.get('POLICY_NAME')
    _ = [policy for policy in _ if policy.name == policy_name]
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
