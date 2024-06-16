#!/usr/bin/env python3

from asyncio import run
from utils import get_adc_token, get_settings, get_projects
from pprint import pprint


async def main():

    try:
        settings = await get_settings()
        access_token = await get_adc_token(quota_project_id=settings.get('quota_project_id'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    return projects

if __name__ == "__main__":

    _ = run(main())
    pprint(_)
