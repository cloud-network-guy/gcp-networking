#!/usr/bin/env python3

from pprint import pprint
from asyncio import run
from file_utils import get_settings
from gcp_utils import get_access_token, get_projects, get_api_data


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    return projects

if __name__ == "__main__":

    _ = run(main())
    pprint(_)
