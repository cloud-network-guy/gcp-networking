#!/usr/bin/env python3

from asyncio import run, gather
from aiohttp import ClientSession
from file_utils import get_settings, write_to_excel, get_calls
from gcp_utils import get_access_token, get_projects, get_api_data
from gcp_classes import ForwardingRule, TargetProxy, SSLCert
from itertools import chain


async def get_forwarding_rules(project_id: str, access_token: str) -> list:

    results = []
    session = ClientSession(raise_for_status=False)

    try:
        # use aggregated call since it's the fastest
        url = f"/compute/v1/projects/{project_id}/aggregated/forwardingRules"
        _ = await get_api_data(session, url, access_token)
        results.extend(_)
    except Exception as e:
        raise RuntimeError(f"Error getting Forwarding Rules: {e}")

    await session.close()
    #return [item for items in results for item in items]  # Flatten results
    return list(chain(*results))


async def get_target_https_proxies(project_id: str, access_token: str, regions: list = []) -> list:

    results = []
    session = ClientSession(raise_for_status=False)
    try:
        urls = [f"/compute/v1/projects/{project_id}/global/targetHttpsProxies"]   # Global
        urls.extend([f"/compute/v1/projects/{project_id}/regions/{region}/targetHttpsProxies" for region in regions])
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results.extend(await gather(*tasks))
    except Exception as e:
        raise RuntimeError(f"Error getting Target HTTPS Proxies: {e}")

    await session.close()
    #return [item for items in results for item in items]  # Flatten results
    return list(chain(*results))

async def get_ssl_certs(project_id: str, access_token: str, name: str, regions: list = []) -> list:

    results = []
    session = ClientSession(raise_for_status=False)
    try:
        urls = [f"/compute/v1/projects/{project_id}/global/sslCertificates"]
        for region in regions:
            urls.append(f"/compute/v1/projects/{project_id}/regions/{region}/sslCertificates")
        tasks = [get_api_data(session, url, access_token) for url in urls]
        results.extend(await gather(*tasks))
    except Exception as e:
        raise RuntimeError(f"Error getting SSL Certs: {e}")

    await session.close()
    #return [item for items in results for item in items]  # Flatten results
    return list(chain(*results))

async def main() -> list:

    from time import time

    start = time()

    print("Reading settings")
    settings = await get_settings()
    cert_issuer = settings.get('cert_issuer')
    cert_subject = settings.get('cert_subject')
    days_threshold = settings.get('days_threshold', 20)

    print("Getting Google ADCs...")
    access_token = await get_access_token(settings.get('key_file'))

    session = ClientSession(raise_for_status=False)

    print("Getting Projects...")
    projects = await get_projects(access_token)
    project_ids = [project.id for project in projects]

    calls = await get_calls()

    print("Getting forwarding rules for", len(project_ids), "Projects...")
    call = calls.get('forwarding_rules')['calls'][0]
    urls = [f"/compute/v1/projects/{project_id}/{call}" for project_id in project_ids]
    #tasks = [make_api_call(url, access_token) for url in urls]
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)

    forwarding_rules = [ForwardingRule(item) for items in results for item in items]
    # Filter to rules that reference an HTTPS Target proxy
    forwarding_rules = [rule for rule in forwarding_rules if 'targetHttpsProxies' in rule.target]
    print("Discovered", len(forwarding_rules), "HTTPS Forwarding Rules")

    # Get a list of active regions for each project to limit the scope of further API calls
    regions_by_project = {project_id: [] for project_id in project_ids}
    for item in forwarding_rules:
        if item.region == "global":
            continue
        project_id = item.project_id
        region = item.region
        regions = regions_by_project.get(project_id, [])
        if region not in regions:
            regions.append(region)
            regions_by_project.update({project_id: regions})
    #print(regions_by_project)
    #quit()

    print("Getting SSL Certificate for", len(project_ids), "Projects...")
    tasks = [get_ssl_certs(project_id, access_token, regions_by_project[project_id]) for project_id in project_ids]
    results = await gather(*tasks)
    ssl_certs = [SSLCert(item) for items in results for item in items]
    
    urls = [f"/compute/v1/projects/{project_id}/global/sslCertificates" for project_id in project_ids]
    for project_id in project_ids:
        for region in regions_by_project[project_id]:
            urls.append(f"/compute/v1/projects/{project_id}/regions/{region}/sslCertificates")
    print(urls)
    tasks = [get_api_data(session, url, access_token) for url in urls]
    #results.extend(await gather(*tasks))
    results = await gather(*tasks)
    ssl_certs = [SSLCert(item) for items in results for item in items]
    #    return [item for items in results for item in items]  # Flatten results

    print("Discovered", len(ssl_certs), "SSL Certificates")

    print(f"Getting Target HTTPS proxies for {len(project_ids)} Projects...")
    #tasks = [get_target_https_proxies(project_id, access_token, regions_by_project[project_id]) for project_id in project_ids]
    #results = await gather(*tasks)
    #target_proxies = [TargetProxy(item) for items in results for item in items]
    urls = [f"/compute/v1/projects/{project_id}/global/targetHttpsProxies" for project_id in project_ids]
    for project_id in project_ids:
        for region in regions_by_project[project_id]:
            urls.append(f"/compute/v1/projects/{project_id}/regions/{region}/targetHttpsProxies")
    tasks = [get_api_data(session, url, access_token) for url in urls]
    results = await gather(*tasks)
    target_proxies = [TargetProxy(item) for items in results for item in items]
    print("Discovered", len(target_proxies), "HTTPS Target proxies...")
    await session.close()

    print("Matching SSL Certificates to Target Proxies...")
    active_certs = {}
    for target_proxy in target_proxies:
        for ssl_cert in target_proxy.ssl_certs:
            active_certs.update({ssl_cert: target_proxy.name})
    print("Discovered", len(active_certs), "SSL certs used by active Target HTTPS proxies")

    certs_to_update = []
    for ssl_cert in ssl_certs:
        if ssl_cert.is_expired:
            continue  # cert expired over 1 week ago; assume we don't care
        if ssl_cert.expire_timestamp < start + days_threshold * 24 * 3600:
            k = f"{ssl_cert.project_id}/{ssl_cert.region}/{ssl_cert.name}"
            if active_certs.get(k):
                certs_to_update.append(ssl_cert)

    print("Found", len(certs_to_update), "certs that expire soon.")

    # Sort so ones expiring soonest are first in the list
    certs_to_update = sorted(certs_to_update, key=lambda x: x.expire_timestamp, reverse=False)
    return [_.__dict__ for _ in certs_to_update]

if __name__ == "__main__":

    from pprint import pprint

    try:
        _ = run(main())
        [pprint(cert) for cert in _]
    except Exception as e:
        raise RuntimeError(e)
