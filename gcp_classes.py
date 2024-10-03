#!/usr/bin/env python3

from datetime import datetime
from time import time


class GCPProject:

    def __init__(self, item: dict):

        self.id = item.get('projectId')
        self.name = item.get('name')
        self.number = int(item.get('projectNumber', 000000000))
        self.state = item.get('lifecycleState', "UNKNOWN")
        self.labels = item.get('labels', {})
        if create_time := item.get('createTime'):
            date_time = f"{create_time[:10]} {create_time[11:19]}"
            self.create_timestamp = int(datetime.timestamp(datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")))
        else:
            self.create_timestamp = 0
        self.creation = str(datetime.fromtimestamp(self.create_timestamp))  

        parent_folder_id = None
        if parent := item.get('parent'):
            if parent.get('type') == 'folder':
                parent_folder_id = parent.get('id')
        self.parent_folder_id = int(parent_folder_id) if parent_folder_id else 000000000

    def __repr__(self):
        return str({k: v for k, v in vars(self).items() if v})

    def __str__(self):
        return str({k: v for k, v in vars(self).items() if v})


class GCPItem:

    def __init__(self, item: dict = {}):

        self.name = item.get('name')
        self.description = item.get('description', "")
        if creation_timestamp := item.get('creationTimestamp'):
            date_time = f"{creation_timestamp[:10]} {creation_timestamp[11:19]}"
            self.creation_timestamp = int(datetime.timestamp(datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")))
        else:
            self.creation_timestamp = 0
        # Convert to human-readable string
        self.creation = str(datetime.fromtimestamp(self.creation_timestamp))  

        if _ := item.get('zone'):
            self.zone = _.split('/')[-1]
            self.region = self.zone[:-2]
        else:
            self.zone = None
            self.region = item.get('region', "/global").split('/')[-1]

        if _ := item.get('selfLink'):
            self.id = _.replace('https://www.googleapis.com/compute/v1/', "")
            self.project_id = _.split('/')[-4 if self.region == 'global' else -5]
        elif _ := item.get('id'):
            self.id = _
            self.project_id = _.split('/')[1]
        else:
            self.id = ""
            self.project_id = "unknown"

        if self.zone:
            self.key = f"{self.project_id}/{self.zone}/{self.name}"
        elif self.region == 'global':
            self.key = f"{self.project_id}/{self.name}"
        else:
            self.key = f"{self.project_id}/{self.region}/{self.name}"

    def __repr__(self):
        return str({k: v for k, v in vars(self).items() if v})

    def __str__(self):
        return str({k: v for k, v in vars(self).items() if v})


class GCPNetworkItem(GCPItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        if self.id.endswith('/networks'):
            self.network = self.id   # This is itself a network, so use its own ID
        if self.id.endswith('/subnetworks'):
            self.subnetwork = self.id   # This is itself a subnet, so use its own ID

        self.network_key = None
        self.network_name = None
        if network := item.get('network'):
            self.network_project_id = network.split('/')[-4]
            self.network_name = network.split('/')[-1]
            self.network_key = f"{self.network_project_id}/{self.network_name}"

        self.subnet_key = None
        self.subnet_name = None
        if subnetwork := item.get('subnetwork'):
            self.network_project_id = subnetwork.split('/')[-5]
            self.region = subnetwork.split('/')[-3]
            self.subnet_name = subnetwork.split('/')[-1]
            self.subnet_key = f"{self.network_project_id}/{self.region}/{self.subnet_name}"


class Network(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.key = f"{self.project_id}/{self.name}"
        self.routing_mode = None
        if routing_config := item.get('routingConfig'):
            self.routing_mode = routing_config.get('routingMode', "UNKNOWN")
        self.peerings = item.get('peerings', [])
        self.subnetworks = item.get('subnetworks', [])
        self.num_subnets = len(self.subnetworks)
        self.mtu = item.get('mtu', 0)
        self.auto_create_subnets = item.get('autoCreateSubnetworks', False)
        self.region = None
        self.subnet_key = None


class Subnet(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.purpose = item.get('purpose', "UNKNOWN")
        if cidr_range := item.get('ipCidrRange'):
            self.cidr_range = cidr_range
            self.usable_ips = (2 ** (32 - int(cidr_range.split('/')[-1]))) - 4

        self.key = f"{self.project_id}/{self.region}/{self.name}"


class CloudRouter(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.interfaces = []
        interfaces = item.get('interfaces', [])
        for interface in interfaces:
            _ = {
                'name': interface.get('name'),
                'ip_range': interface.get('ipRange'),
            }
            if linked_vpn_tunnel := interface.get('linkedVpnTunnel'):
                _.update({'linked_vpn_tunnel': linked_vpn_tunnel.split('/')[-1]})
            if linked_interconnect_attachment := interface.get('linkedInterconnectAttachment'):
                _.update({
                    'linked_interconnect_attachment': linked_interconnect_attachment.split('/')[-1],
                    'management_type': interface.get('managementType'),
                })
            self.interfaces.append(_)

        self.bgp_peers = []
        bgp_peers = item.get('bgpPeers', [])
        for bgp_peer in bgp_peers:
            _ = {
                'name': bgp_peer.get('name'),
                'ip_address': bgp_peer.get('ipAddress'),
                'peer_ip_address': bgp_peer.get('peerIpAddress'),
                'peer_asn': bgp_peer.get('peerAsn'),
                'advertised_route_priority': bgp_peer.get('advertisedRoutePriority', 100),
                'advertise_mode': bgp_peer.get('advertiseMode'),
            }
            self.bgp_peers.append(_)

        self.cloud_nats = [CloudNat(nat) for nat in item.get('nats', [])]
        self.nat_ips = []

    def get_routes(self):
        pass

    async def get_status(self):
        pass


class CloudNat(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.ip_allocation_option = item.get('natIpAllocateOption', "UNKNOWN")
        self.min_ports_per_vm = item.get('minPortsPerVm', 0)
        self.max_ports_per_vm = item.get('maxPortsPerVm', 0)
        self.enable_dpa = item.get('enableDynamicPortAllocation')
        self.enable_eim = item.get('enableEndpointIndependentMapping')
        self.ips = []
        for nat_ip in item.get('natIps', []):
            _ = nat_ip.split('/')[-1]
            self.ips.append(_)


class FirewallRule(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.region = None
        self.subnet_key = None


class ForwardingRule(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.ip_address = item.get('IPAddress', "UNKNOWN")
        self.lb_scheme = item.get('loadBalancingScheme', "UNKNOWN").upper()
        self.is_internal = True if self.lb_scheme.startswith("INTERNAL") else False
        self.is_external = True if self.lb_scheme.startswith("EXTERNAL") else False
        self.is_managed = True if self.lb_scheme.endswith("_MANAGED") else False

        if target := item.get('target'):
            self.target = target.replace('https://www.googleapis.com/compute/v1/', "")
        else:
            self.target = ""
        if port_range := item.get('portRange'):
            self.ports = str(port_range.split("-"))
        else:
            self.ports = item.get('ports', "all")


class TargetProxy(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)
        self.ssl_certs = []
        for ssl_cert in item.get('sslCertificates', []):
            name = ssl_cert.split('/')[-1]
            self.ssl_certs.append(f"{self.project_id}/{self.region}/{name}")


class CloudVPNGateway(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.vpn_ips = [vpn_interface['ipAddress'] for vpn_interface in item.get('vpnInterfaces', [])]
        self.subnet_key = None


class PeerVPNGateway(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.vpn_ips = [vpn_interface['ipAddress'] for vpn_interface in item.get('vpnInterfaces', [])]
        self.interface_ips = [interface['ipAddress'] for interface in item.get('interfaces', [])]
        self.redundancy_type = item.get('redundancyType', "UNKNOWN")
        self.region = None
        self.network_key = None
        self.subnet_key = None


class VPNTunnel(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.vpn_gateway = None
        if vpn_gateway := item('vpnGateway'):
            self.vpn_gateway = vpn_gateway.split('/')[-1]
        self.interface = item.get('vpnGatewayInterface')
        self.peer_gateway = None
        if peer_external_gateway := item.get('peerExternalGateway'):
            self.peer_gateway = peer_external_gateway.split('/')[-1]
        self.peer_ip = item.get('peerIp')
        self.ike_version = item.get('ikeVersion', 0)
        self.status = item.get('status')
        self.detailed_status = item.get('detailedStatus')
        self.network_key = None
        self.subnet_key = None


class Instance(GCPItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        # Information about the instance
        self.name = item.get('name')
        self.zone = item.get('zone', "unknown-0").split('/')[-1]
        self.region = self.zone[:-2]
        self.machine_type = item.get('machineType', "unknown/unknown").split('/')[-1]
        self.ip_forwarding = item.get('canIpForward', False)
        self.status = item.get('status', "UNKNOWN")
        self.nics = [InstanceNic(nic) for nic in item.get('networkInterfaces', [])]


class InstanceNic(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.ip_address = item.get('networkIP')
        self.network_key = None
        if network := item.get('network'):
            self.network_name = network.split("/")[-1]
            self.network_project_id = network.split("/")[-4]
            self.network_key = f"{self.network_project_id}/{self.network_name}"
            self.subnet_key = None
            if subnetwork := item.get('subnetwork'):
                self.subnet_name = subnetwork.split('/')[-1]
                self.region = subnetwork.split('/')[-3]
                self.subnet_key = f"{self.network_project_id}/{self.region}/{self.subnet_name}"

            # Also check if the instance has any active NAT IP addresses
            self.access_config_name = None
            self.access_config_type = None
            self.external_ip_address = None
            if access_configs := item.get('accessConfigs'):
                for access_config in access_configs:
                    self.access_config_name = access_config.get('name', "UNKNOWN")
                    self.access_config_type = access_config.get('type', "UNKNOWN")
                    self.external_ip_address = access_config.get('natIP', "UNKNOWN")


class SSLCert(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        from cryptography.x509 import load_pem_x509_certificate
        from cryptography.x509.oid import NameOID

        super().__init__(item)

        self.type = item.get('type', "UNKNOWN")
        self.is_expired = False
        self.is_expiring_soon = False

        self.issuer = "UNKNOWN"
        self.subject = "UNKNOWN"
        self.cn = "UNKNOWN"
        if certificate := item.get('certificate'):
            if managed := item.get('managed'):
                self.issuer = "Google"
                domains = managed.get('domains', [])
                if len(domains) > 0:
                    self.cn = domains[0]
            else:
                # Get CN from the cert itself
                _ = load_pem_x509_certificate(certificate.encode('utf-8'))
                self.issuer = _.issuer.rfc4514_string()
                self.subject = _.subject.rfc4514_string()
                common_name = _.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                self.cn = common_name[0].value
            if sans := item.get('subjectAlternativeNames', []):
                # Cert is SAN, so won't have Common Name
                for san in sans:
                    if not san.startswith('*'):
                        # Use first non-wildcard hostname
                        self.cn = san
                        break
                if len(sans) > 0:
                    self.cn = sans[0]   # only has wildcards, so just use the first one

        if expire_time := item.get('expireTime'):
            _ = f"{expire_time[:10]} {expire_time[11:19]}"  # reformat to <date> <time>
            self.expire_timestamp = int(datetime.timestamp(datetime.strptime(_, "%Y-%m-%d %H:%M:%S")))
        else:
            self.expire_timestamp = 0
        self.expire_str = str(datetime.fromtimestamp(self.expire_timestamp))  # Convert to human-readable string

        now = int(time())

        if self.expire_timestamp < now:
            self.is_expired = True

        if self.expire_timestamp < now + 21 * 24 * 3600:
            self.is_expiring_soon = True


class GKECluster(GCPItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.endpoint_ips = []
        if private_cluster_config := item.get('privateClusterConfig'):
            if public_endpoint := private_cluster_config.get('publicEndpoint'):
                self.endpoint_ips.append(public_endpoint)
            if private_cluster_config.get('enablePrivateEndpoint'):
                if private_endpoint := private_cluster_config.get('privateEndpoint'):
                    self.endpoint_ips.append(private_endpoint)

        self.network_project_id = "unknown"
        self.network_name = "unknown"
        if network_config := item.get('networkConfig'):
            if network := network_config.get('network'):
                self.network_project_id = network.split('/')[-4]
                self.network_name = network.split('/')[-1]
        self.network_key = f"{self.network_project_id}/{self.network_name}"


        """
        if node_pools := item.get('nodePools'):
            if network_config := node_pools[0].get('networkConfig'):
                if network := network_config.get('network'):
                    self.network_project_id = network.split('/')[-4]
                    self.network_name = network.split('/')[-1]
        self.network_key = f"{self.network_project_id}/{self.network_name}"
        """
        location = item.get('location', "unknown-0")
        self.region = location.split("/")[-1][:-2] if location[-2] == '-' else location


class CloudSQL(GCPItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.project_id = item.get('project', "UNKNOWN")
        self.ip_addresses = []
        if settings := item.get('settings'):
            if ip_configuration := settings.get('ipConfiguration'):
                if network := ip_configuration.get('privateNetwork'):
                    self.network_project_id = network.split('/')[-4]
                    self.network_name = network.split('/')[-1]
                    self.network_key = f"{self.network_project_id}/{self.network_name}"
            for ip_address in item.get('ipAddresses', []):
                _ = ip_address.get('ipAddress')
                self.ip_addresses.append(_)


class SecurityPolicy(GCPNetworkItem):

    def __init__(self, item: dict = {}):

        super().__init__(item)

        self.rules = []

        for rule in item.get('rules'):
            self.rules.append({
                'description': rule.get('description', ""),
                'priority': int(rule.get('priority', 0)),
                'action': rule.get('action'),
                'preview': rule.get('preview', False),
                'match': rule.get('match', {}),
            })
