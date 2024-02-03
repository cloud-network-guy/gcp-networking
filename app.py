#!/usr/bin/env python3

from quart import Quart, jsonify, render_template, request, Response, session
#from flask import Flask, jsonify, render_template, request, Response, session
from traceback import format_exc
from utils import get_version, get_settings

RESPONSE_HEADERS = {'Cache-Control': "no-cache, no-store"}
CONTENT_TYPE = "text/plain"

app = Quart(__name__, static_url_path='/static')
#app = Flask(__name__, static_url_path='/static')


@app.route("/version")
async def _version():

    try:
        _ = await get_version(vars(request))
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


@app.route("/get-projects")
async def _projects():

    from utils import get_adc_token, get_projects
    #from gcp_operations import get_projects

    try:
        settings = await get_settings()
        access_token = await get_adc_token(quota_project_id=settings.get('quota_project_id'))
        projects = await get_projects(access_token, sort_by='create_timestamp')
        _ = [project.__dict__ for project in projects]
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


@app.route("/rancid")
async def _rancid():

    from rancid import main

    try:
        _ = await main()
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


@app.route("/check-quotas")
async def _check_quotas():

    from check_quotas import main

    try:
        _ = await main()
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


@app.route("/check-ssl-certs")
async def _check_ssl_certs():

    from check_ssl_certs import main

    try:
        _ = await main()
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


if __name__ == '__main__':
    app.run(debug=True)
