#!/usr/bin/env python3

from traceback import format_exc
from quart import Quart, jsonify, render_template, request, Response, session
from file_utils import get_version, get_settings
from gcp_utils import *

JSON_RESPONSE_HEADERS = {'Cache-Control': "no-cache, no-store"}
PLAIN_CONTENT_TYPE = "text/plain"

app = Quart(__name__, static_url_path='/static')


@app.route("/version")
async def _version():

    try:
        _ = await get_version(vars(request))
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/profiles")
async def _profiles():

    try:
        settings = await get_settings()
        profiles = settings.get('profiles')
        return jsonify(profiles), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/projects")
async def _projects():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        projects = await get_projects(access_token)
        return jsonify([p.__dict__ for p in projects]), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/service-projects")
async def _service_projects():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        host_project_id = settings.get('host_project_id')
        service_projects = await get_service_projects(host_project_id, access_token)
        _ = {
            'host_project_id': host_project_id,
            'service_projects': service_projects,
        }
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/networks")
async def _networks():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        host_project_id = settings.get('host_project_id')
        networks = await get_networks(host_project_id, access_token)
        options = request.args
        filters = {}
        if _profile := options.get('profile'):
            if profiles := settings.get('profiles'):
                if profile := profiles.get(_profile):
                    filters.update({'profile': profile})
                else:
                    raise f"profile '{_profile}' not found in settings file"
            else:
                raise f"no profiles found in settings file"
            relevant_networks = None
            if network_string := profile.get('network_string'):
                print(profile, network_string)
                relevant_networks = [n.name for n in networks if network_string in n.name]
            else:
                relevant_networks = [options.get('network')] if 'network' in options else options.get('networks')
            networks = [n for n in networks if n.name in relevant_networks]
        return jsonify([n.__dict__ for n in networks]), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/subnets")
async def _subnets():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        host_project_id = settings.get('host_project_id')
        options = request.args
        regions = [options.get('region')] if 'region' in options else options.get('regions')
        subnets = await get_subnets(host_project_id, access_token, regions=regions)
        filters = {}
        relevant_networks = None
        if _profile := options.get('profile'):
            if profiles := settings.get('profiles'):
                if profile := profiles.get(_profile):
                    filters.update({'profile': profile})
                else:
                    raise f"profile '{_profile}' not found in settings file"
            else:
                raise f"no profiles found in settings file"
            if network_string := profile.get('network_string'):
                print(profile, network_string)
                #host_project_id = settings.get('host_project_id')
                #networks = await get_networks(host_project_id, access_token)
                relevant_networks = [s.network_name for s in subnets if network_string in s.network_name]
            else:
                relevant_networks = [options.get('network')] if 'network' in options else options.get('networks')
            #subnets
            #networks = [n for n in networks if n.name in relevant_networks]

        #filters = {
        #    'regions': [options.get('region')] if 'region' in options else options.get('regions'),
        #    'networks': relevant_networks,
        #}
        #regions = [options.get('region')] if 'region' in options else options.get('regions')]
        #subnets = await get_subnets(host_project_id, access_token, regions=regions)
        if relevant_networks:
            subnets = [s for s in subnets if s.network_name in relevant_networks]
        """
        filters = {
            'regions': [options.get('region')] if 'region' in options else options.get('regions'),
            'networks': [options.get('network')] if 'network' in options else options.get('networks'),
        }
        if _ := filters.get('networks'):
            _filtered_subnets = []
            for n in _:
                _filtered_subnets.extend([s for s in subnets if s.network_name == n])
            subnets = _filtered_subnets
        """
        tasks = [s.get_bindings(access_token) for s in subnets]
        _ = await gather(*tasks)
        projects = await get_projects(access_token)
        for s in subnets:
            s.attached_projects = []
            for p in projects:
                if f"serviceAccount:{p.number}-compute@developer.gserviceaccount.com" in s.members:
                    s.attached_projects.append(p.id)
                    #print(s)
        return jsonify([s.__dict__ for s in subnets]), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/rancid")
async def _rancid():

    from rancid import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/check-quotas")
async def _check_quotas():

    from check_quotas import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/check-ssl-certs")
async def _check_ssl_certs():

    from check_ssl_certs import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/list-access-configs")
async def _list_access_configs():

    from list_access_configs import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/ip-addresses")
async def _ip_addresses():

    from ip_addresses import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/empty-subnets")
async def _empty_subnets():

    from get_empty_subnets import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/gke-clusters")
async def _gke_clusters():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        projects = await get_projects(access_token)
        tasks = [p.get_gke_clusters(access_token) for p in projects]
        _ = await gather(*tasks)
        gke_clusters = []
        for p in projects:
            gke_clusters.extend(p.gke_clusters)
        return jsonify([c.__dict__ for c in gke_clusters]), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/recent-firewall-rules")
async def _recent_firewall_rules():

    from recent_firewall_rules import main

    try:
        _ = await main()
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/")
async def _root():

    try:
        fields = ('Option', 'Description')
        options = {
            'projects': "List all Projects",
            'service-projects': "List all Shared VPC Service Projects",
            'networks': "List all VPC Networks",
            'subnets': "List all Subnetworks",
        }
        data = []
        for option, description in options.items():
            data.append({
                'Option': option,
                'Description': description,
            })
        return await render_template(
            template_name_or_list='index.html',
            title="Menu",
            fields=fields,
            data=data,
        )
    except Exception as e:
        return Response(format_exc(), status=500, content_type=PLAIN_CONTENT_TYPE)


if __name__ == '__main__':
    app.run(debug=True)
