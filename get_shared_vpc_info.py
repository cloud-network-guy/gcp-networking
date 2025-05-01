from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings
from gcp_utils import get_access_token, get_projects, get_host_project, get_networks, get_subnets, get_subnet_iam_binding


async def main():

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    project_numbers_to_id = {p.number: p.id for p in projects}
    
    session = ClientSession(raise_for_status=False)

    # Get the Shared VPC host project for each service project
    tasks = [get_host_project(p.id, access_token, session) for p in projects]
    results = await gather(*tasks)
    results = dict(zip([p.id for p in projects], results))

    # Form new dictionary with Service Project ID as key, host project ID as value
    xvpc_service_projects = {sp: hp for sp, hp in results.items() if hp}
    # Also create a dictionary of host projects with 
    xvpc_host_projects = {k: [] for k in set(xvpc_service_projects.values())}
    
    # Get all networks defined in the host project
    xvpc_networks = {xvpc_host_project: [] for xvpc_host_project in xvpc_host_projects.keys()}
    for host_project_id in xvpc_host_projects.keys():
        _ = await get_networks(host_project_id, access_token, session)
        xvpc_networks.update({host_project_id: _})

    # Get all subnets defined in the host project
    subnets = {xvpc_host_project: [] for xvpc_host_project in xvpc_host_projects.keys()}
    for host_project_id in xvpc_host_projects.keys():
        _ = await get_subnets(host_project_id, access_token, session)
        subnets.update({host_project_id: _})
    all_subnets = []
    for v in subnets.values():
        all_subnets.extend(v)


    # Get bindings for each Subnet
    tasks = [s.get_bindings(access_token, session) for s in all_subnets]
    _ = await gather(*tasks)
    subnet_bindings = {s.key: s.members for s in all_subnets}
    for host_project_id, members in xvpc_host_projects.items():
        members = []
        for s in all_subnets:
            if s.network_project_id == host_project_id:
                if s.members:
                    members.extend(s.members)
        xvpc_host_projects.update({host_project_id: members})
    for k, v in subnet_bindings.items():
        if v and len(v) == 0:
            print(k, v)

    # Find orphans (service projects that don't have any subnet bindings)
    orphans = []
    service_accounts = {p.id: f"serviceAccount:{p.number}-compute@developer.gserviceaccount.com" for p in projects}
    for project_id, service_account in service_accounts.items():
        if project_id in xvpc_host_projects:
            print("Skipping", project_id, "as it's a shared VPC host project")
            continue
        if host_project_id := xvpc_service_projects.get(project_id):
            members = xvpc_host_projects.get(host_project_id, [])
            #print(service_account)
            if service_account not in members:
                print("Project ID", project_id, "is missing permissions for", service_account)
                orphans.append(project_id)
        else:
            print("No shared VPC found for project ID", project_id)
            continue

    await session.close()
    print("Found", len(orphans), "orphans:", orphans)
    

if __name__ == "__main__":

    try:
        _ = run(main())
    except Exception as e:
        raise RuntimeError(e)
