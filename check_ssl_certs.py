from asyncio import run, gather
from time import time
from pprint import pprint
from gcp_operations import make_api_call
from utils import get_settings, get_adc_token, get_calls, get_projects
from main import *


async def get_forwarding_rules(project_id: str, access_token: str) -> list:

    results = []
    try:
        # use aggregated call since it's the fastest
        url = f"/compute/v1/projects/{project_id}/aggregated/forwardingRules"
        _ = await make_api_call(url, access_token)
        results.extend(_)
    except Exception as e:
        raise f"Error getting Forwarding Rules: {e}"
    return results


async def get_target_https_proxies(project_id: str, access_token: str, regions: list = []) -> list:

    results = []
    try:
        urls = [f"/compute/v1/projects/{project_id}/global/targetHttpsProxies"]   # Global
        urls.extend([f"/compute/v1/projects/{project_id}/regions/{region}/targetHttpsProxies" for region in regions])
        tasks = [make_api_call(url, access_token) for url in urls]
        results.extend(await gather(*tasks))
        return [item for items in results for item in items]  # Flatten results
    except Exception as e:
        raise f"Error getting Target HTTPS Proxies: {e}"


async def get_ssl_certs(project_id: str, access_token: str, name: str, regions: list = []) -> list:

    results = []
    try:
        urls = [f"/compute/v1/projects/{project_id}/global/sslCertificates"]
        for region in regions:
            urls.append(f"/compute/v1/projects/{project_id}/regions/{region}/sslCertificates")
        tasks = [make_api_call(url, access_token) for url in urls]
        results.extend(await gather(*tasks))
        return [item for items in results for item in items]  # Flatten results
    except Exception as e:
        raise f"Error getting SSL Certs: {e}"


async def main() -> list:

    start = time()

    print("Reading settings")
    settings = await get_settings()
    cert_issuer = settings.get('cert_issuer')
    cert_subject = settings.get('cert_subject')
    days_threshold = settings.get('days_threshold', 14)

    print("Getting Google ADCs...")
    access_token = await get_adc_token(quota_project_id=settings.get('quota_project_id'))

    print("Getting Projects...")
    #project_ids = await get_prxoject_ids(access_token)
    projects = await get_projects(access_token)
    project_ids = [project.id for project in projects]

    #session = None #await start_session()

    calls = await get_calls()

    print("Getting forwarding rules for", len(project_ids), "Projects...")

    #tasks = [get_forwarding_rules(project_id, access_token) for project_id in project_ids]
    #results = await gather(*tasks)

    call = calls.get('forwarding_rules')['calls'][0]     
    urls = [f"/compute/v1/projects/{project_id}/{call}" for project_id in project_ids]
    tasks = [make_api_call(url, access_token) for url in urls]
    results = await gather(*tasks)

    forwarding_rules = [ForwardingRule(item) for items in results for item in items]
    # Filter to rules that reference an HTTPS Target proxy
    forwarding_rules = [rule for rule in forwarding_rules if 'targetHttpsProxies' in rule.target]
    print("Discovered", len(forwarding_rules), "HTTPS Forwarding Rules")

    #print(forwarding_rules)
    #  determine which region(s) each project uses

    regions_by_project = {project_id: [] for project_id in project_ids}
    for item in forwarding_rules:
        project_id = item.project_id
        region = item.region
       # print(project_id, region)
        regions = regions_by_project.get(project_id, [])
        if region not in regions:
            regions.append(region)
            #print(project_id, regions)
            regions_by_project.update({project_id: regions})
    #print(regions_by_project['otl-csd-ops-archive-ctr'])

    print("Getting SSL Certificate for", len(project_ids), "Projects...")
    tasks = [get_ssl_certs(project_id, access_token, regions_by_project[project_id]) for project_id in project_ids]
    results = await gather(*tasks)
    ssl_certs = [SSLCert(item) for items in results for item in items]
    print("Discovered", len(ssl_certs), "SSL Certificates")

    print(f"Getting Target HTTPS proxies for {len(project_ids)} Projects...")
    tasks = [get_target_https_proxies(project_id, access_token, regions_by_project[project_id]) for project_id in project_ids]
    results = await gather(*tasks)
    target_proxies = [TargetProxy(item) for items in results for item in items]
    print("Discovered", len(target_proxies), "HTTPS Target proxies...")

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

    try:
        _ = run(main())
        [pprint(cert) for cert in _]
    except Exception as e:
        raise e
