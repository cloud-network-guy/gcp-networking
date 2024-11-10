from gcp_utils import *
from asyncio import run

access_token = run(get_access_token())
projects = run(get_projects(access_token))
print(projects)
