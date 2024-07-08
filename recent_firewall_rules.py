#!/usr/bin/env python3 

from gcp_operations import make_api_call
from utils import get_adc_token, get_projects
from asyncio import run, gather
from time import time
from main import *


async def main():

    try:
        access_token = await get_adc_token()
        projects = await get_projects(access_token)
    except Exception as e:
        quit(e)

    urls = [f"/compute/v1/projects/{project.id}/global/firewalls" for project in projects]
    tasks = [make_api_call(url, access_token) for url in urls]
    results = await gather(*tasks)
    _ = [item for items in results for item in items]  # Flatten results
    firewall_rules = [FirewallRule(_) for _ in _]

    now = int(time())
    for firewall_rule in firewall_rules:
        if now - firewall_rule.creation_timestamp < 3600 * 72:
            print(firewall_rule.name, firewall_rule.creation_timestamp)

if __name__ == "__main__":

    _ = run(main())
