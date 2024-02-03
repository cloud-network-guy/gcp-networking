#!/usr/bin/env python3 


from gcp_operations import make_gcp_call
from utils import get_adc_token, get_projects
from asyncio import run, gather, create_task
import csv

CSV_FILE = 'gcp_ip_addresses.csv'


async def get_instance_nics(project_id: str, access_token: str) -> list:

    try:
        api_name = "compute"
        call = f"/compute/v1/projects/{project_id}/aggregated/instances"
        _ = await make_gcp_call(call, access_token, api_name)
        items = _.get('items')
    except:
        return []

    results = []
    for item in items:
        for nic in item.get('networkInterfaces', []):
            if network := nic.get('network'):
                network_name = network.split("/")[-1]
                network_project_id = network.split("/")[-4]
                zone = item.get('zone', "null/unknown-0")
                region = zone.split("/")[-1][:-2]
                results.append({
                    'ip_address': nic.get('networkIP'),
                    'type': "GCE Instance NIC",
                    'name': item['name'],
                    'project_id': project_id,
                    'network_id': f"{network_project_id}/{network_name}",
                    'region': region,
                })
                # Also check if the instance has any active NAT IP addresses
                if access_configs := nic.get('accessConfigs'):
                    for access_config in access_configs:
                        if ip_address := access_config.get('natIP'):
                            results.append({
                                'ip_address': ip_address,
                                'type': "GCE Instance NAT IP",
                                'name': access_config['name'],
                                'project_id': project_id,
                                'network_id': "n/a",
                                'region': region,
                            })
    return results


async def get_fwd_rules(project_id: str, access_token: str) -> list:

    try:
        api_name = "compute"
        calls = [
            f"/compute/v1/projects/{project_id}/aggregated/forwardingRules",
            f"/compute/v1/projects/{project_id}/global/forwardingRules",
        ]
        items = []
        for call in calls:
            _ = await make_gcp_call(call, access_token, api_name)
            items.extend(_.get('items'))
    except:
        return []

    results = []
    for item in items:
        if network := item.get('network'):
            network_project_id = network.split("/")[-4]
            network_name = network.split("/")[-1]
            network_id = f"{network_project_id}/{network_name}"
        else:
            network_id = "n/a"
        results.append({
            'ip_address': item.get('IPAddress'),
            'type': "Forwarding Rule",
            'name': item['name'],
            'project_id': project_id,
            'network_id': network_id,
            'region': item.get('region', "global-0").split("/")[-1],
        })
    return results


async def get_cloudsql_instances(project_id: str, access_token: str) -> list:

    try:
        api_name = "sqladmin"
        call = f"/v1/projects/{project_id}/instances"
        _ = await make_gcp_call(call, access_token, api_name)
        items = _.get('items')
    except:
        return []

    results = []
    for item in items:
        if not item:
            break
        network_project_id = "unknown"
        network_name = "unknown"
        if ip_configuration := item['settings'].get('ipConfiguration'):
            if network := ip_configuration.get('privateNetwork'):
                network_project_id = network.split("/")[-4]
                network_name = network.split("/")[-1]
        for address in item.get('ipAddresses', []):
            results.append({
                'ip_address': address.get('ipAddress'),
                'type': "Cloud SQL Instance",
                'name': item['name'],
                'project_id': project_id,
                'network_id': f"{network_project_id}/{network_name}",
                'region': item.get('region', "unknown"),
            })
    return results


async def get_gke_endpoints(project_id: str, access_token: str) -> list:

    try:
        api_name = "container"
        call = f"/v1/projects/{project_id}/locations/-/clusters"
        _ = await make_gcp_call(call, access_token, api_name)
        clusters = _.get('items')
    except:
        return []

    results = []
    for cluster in clusters:
        network_project_id = "unknown"
        network_name = "unknown"
        endpoint_ips = []
        if private_cluster_config := cluster.get('privateClusterConfig'):
            endpoint_ips.append(private_cluster_config.get('publicEndpoint'))
            if private_cluster_config.get('enablePrivateEndpoint'):
                endpoint_ips.append(private_cluster_config.get('privateEndpoint'))
        if node_pools := cluster.get('nodePools'):
            if network_config := node_pools[0].get('networkConfig'):
                if network := network_config.get('network'):
                    network_project_id = network.split("/")[-4]
                    network_name = network.split("/")[-1]
        location = cluster.get('location', "unknown-0")
        for endpoint_ip in endpoint_ips:
            results.append({
                'ip_address': endpoint_ip,
                'type': "GKE Endpoint",
                'name': cluster['name'],
                'project_id': project_id,
                'network_id': f"{network_project_id}/{network_name}",
                'region': location.split("/")[-1][:-2] if location[-2] == '-' else location,
                #'pods_range': cluster.get('clusterIpv4Cidr'),
                #'services_range': cluster.get('servicesIpv4Cidr'),
                #'masters_range': cluster['privateClusterConfig']['masterIpv4CidrBlock'] if 'privateClusterConfig' in cluster else None,
            })
    return results


async def get_cloud_nats(project_id: str, access_token: str) -> list:

    try:
        api_name = "compute"
        call = f"/compute/v1/projects/{project_id}/aggregated/routers"
        _ = await make_gcp_call(call, access_token, api_name)
        routers = _.get('items')
    except:
        return []

    cloud_nats = []
    for router in routers:
        if len(router.get('nats', [])) > 0:
            cloud_nats.append({
                'router_name': router['name'],
                'network_name': router.get('network', '/unknown').split('/')[-1],
                'region': router.get('region', "unknown-0").split('/')[-1],
            })

    results = []
    for cloud_nat in cloud_nats:
        router_name = cloud_nat['router_name']
        region = cloud_nat['region']
        try:
            api_name = "compute"
            call = f"/compute/v1/projects/{project_id}/regions/{region}/routers/{router_name}/getRouterStatus"
            _ = await make_gcp_call(call, access_token, api_name)
            router_statuses = _.get('items')
            #print(router_statuses)
        except:
            continue
        for router_status in router_statuses:
            if nat_statuses := router_status.get('natStatus'):
                for nat_status in nat_statuses:
                    nat_ips = []
                    nat_ips.extend(nat_status.get('autoAllocatedNatIps', []))
                    nat_ips.extend(nat_status.get('userAllocatedNatIps', []))
                    for nat_ip in nat_ips:
                        results.append({
                            'ip_address': nat_ip,
                            'type': "Cloud NAT",
                            'name': nat_status.get('name', router_name),
                            'project_id': project_id,
                            'network_id': f"{project_id}/{cloud_nat['network_name']}",
                            'region': region,
                       })
    return results


async def main():

    try:
        access_token = await get_adc_token()
        projects = await get_projects(access_token)
    except Exception as e:
        quit(e)

    print("Gathering IP addresses across", len(projects), "projects...")

    tasks = []
    for project in projects:
        project_id = project.id
        tasks.append(create_task(get_instance_nics(project_id, access_token)))
        tasks.append(create_task(get_fwd_rules(project_id, access_token)))
        tasks.append(create_task(get_cloud_nats(project_id, access_token)))
        tasks.append(create_task(get_cloudsql_instances(project_id, access_token)))
        tasks.append(create_task(get_gke_endpoints(project_id, access_token)))

    ip_addresses = []
    for _ in await gather(*tasks):
        ip_addresses.extend(_)

    return ip_addresses

if __name__ == "__main__":

    _ = run(main())
    data = sorted(_, key=lambda x: x['ip_address'], reverse=False)
    csvfile = open(CSV_FILE, 'w', newline='')
    writer = csv.writer(csvfile)
    writer.writerow(data[0].keys())
    [writer.writerow(row.values()) for row in data]
    csvfile.close()
