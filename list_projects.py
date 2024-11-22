from gcp_utils import *
from asyncio import run
from pprint import pprint

access_token = run(get_access_token())
projects = run(get_projects(access_token))
pprint(projects)
