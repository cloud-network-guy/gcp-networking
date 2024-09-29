#!/usr/bin/env python3

from traceback import format_exc
from quart import Quart, jsonify, render_template, request, Response, session
from file_utils import get_version, get_settings
from gcp_utils import get_access_token, get_projects

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

if __name__ == '__main__':
    app.run(debug=True)
