#!/usr/bin/env python3

from traceback import format_exc
from quart import Quart, jsonify, render_template, request, Response, session
from file_utils import get_version, get_settings
from gcp_utils import get_access_token, get_projects, get_service_projects, get_networks

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
        return jsonify([n.__dict__ for n in networks]), JSON_RESPONSE_HEADERS
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
