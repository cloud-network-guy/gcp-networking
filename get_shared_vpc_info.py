from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import Network, Subnet



async def main() -> list:

    try:
        settings = await get_settings()
        access_token = await get_access_token(settings.get('key_file'))
    except Exception as e:
        quit(e)

    projects = await get_projects(access_token)
    project_ids = [project.id for project in projects]
    #print(project_ids)

    session = ClientSession(raise_for_status=False)

    # Get the Shared VPC host project for each service project
    urls = [f"/compute/v1/projects/{pid}/getXpnHost" for pid in project_ids]
    print(urls)
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    results = dict(zip(project_ids, results))
    print("Get xpn host", results)
    await session.close()

    # Form new dictionary with Service Project ID as key, host project ID as value
    xvpc_service_projects = {pid: info[0].get('name') for pid, info in results.items() if len(info) > 0}
    xvpc_host_projects = set(xvpc_service_projects.values())
    print(xvpc_host_projects)
    # Get all networks defined in the host project
    xvpc_networks = {xvpc_host_project: [] for xvpc_host_project in xvpc_host_projects}
    for host_project in xvpc_host_projects:
        url = f"/compute/v1/projects/{host_project}/global/networks"
        _ = get_api_data(session, url, access_token)
        xvpc_networks.update({host_project: [Network(item) for item in _]})

    # Get all subnets defined in the host project
    subnets = {xvpc_host_project: [] for xvpc_host_project in xvpc_host_projects}
    for host_project in xvpc_host_projects:
        url = f"/compute/v1/projects/{host_project}/aggregated/subnetworks"
        _ = get_api_data(session, url, access_token)
        subnets.update({host_project: [Subnet(item) for item in _]})
    all_subnets = []
    for v in subnets.values():
        all_subnets.extend(v)

    # Get bindings for each Subnet
    subnet_bindings = {subnet.key: [] for subnet in all_subnets}
    for host_project, subnets in subnets.items():
        urls = [f"/compute/v1/projects/{host_project}/regions/{s.region}/subnetworks/{s.name}/getIamPolicy" for s in subnets]
        tasks = [get_api_data(session, url, access_token) for url in urls]
        _ = await gather(*tasks)
        results = dict(zip([_.key for _ in all_subnets], _))
        for subnet_key, data in results.items():
            if bindings := data.get('bindings'):
                for binding in bindings:
                    if binding.get('role') == 'roles/compute.networkUser':
                        if members := binding.get('members', []):
                            members = [member for member in members if not member.startswith('deleted')]
            else:
                members = []
            subnet_bindings.update({subnet_key: members})

        print(subnet_bindings)

        result = results[0]
        if bindings := result.get('bindings'):
            for binding in bindings:
                if binding.get('role') == 'roles/compute.networkUser':
                    if members := binding.get('members', []):
                        members = [member for member in members if not member.startswith('deleted')]
                        xvpc_host_projects[host_project] = members
        print(_)

    quit()
    orphans = []
    service_accounts = {p.id: f"serviceAccount:{p.number}-compute@developer.gserviceaccount.com" for p in projects}
    #service_accounts = {p.id: f"serviceAccount:{p.number}@container-engine-robot.iam.gserviceaccount.com" for p in projects}
    for project_id, service_account in service_accounts.items():
        if project_id in xvpc_host_projects.keys():
            #print("Skipping", project_id, "as it's a shared VPC host project")
            continue
        if host_project_id := xvpc_service_projects.get(project_id):
            members = xvpc_host_projects.get(host_project_id, [])
            if service_account not in members:
                print("Project ID", project_id, "is missing permissions for", service_account)
                orphans.append(project_id)
        else:
            #print("No shared VPC found for project ID", project_id)
            continue

    print(len(orphans))
    #quit()
    for orphan in orphans:
        project = [p for p in projects if p.id == orphan]
        print(project)
    quit()

    xvpc_host_projects = {}
    for project_id, result in results.items():
        if len(result) > 0:
            if xvpc_host_project := result[0].get('name'):
                xvpc_host_projects.update({project_id: xvpc_host_project})
            else:
                print(project_id)
        else:
            print(project_id)


if __name__ == "__main__":

    try:
        _ = run(main())
    except Exception as e:
        raise e
