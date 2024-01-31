from flask import Flask, jsonify, render_template, request, Response, session
from asyncio import run
from traceback import format_exc
from main import get_version, get_settings


app = Flask(__name__, static_url_path='/static')

RESPONSE_HEADERS = {'Cache-Control': "no-cache, no-store"}
CONTENT_TYPE = "text/plain"


@app.route("/version")
def _version():

    try:
        _ = run(get_version(request))
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format(e), status=500, content_type=CONTENT_TYPE)


@app.route("/rancid")
async def _rancid():

    from rancid import main

    try:
        _ = await main()
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


@app.route("/projects")
async def _projects():

    from auth_operations import get_adc_token
    from gcp_operations import get_projects

    try:
        settings = await get_settings()
        access_token = await get_adc_token(quota_project_id=settings.get('quota_project_id'))
        _ = await get_projects(access_token, sort_by='created')
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), status=500, content_type=CONTENT_TYPE)


@app.route("/check_quotas")
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


@app.route("/")
def _root():
    try:
        _ = {'test1': 1, 'test2': [], 'test3': {'a': 3}}
        return jsonify(_), RESPONSE_HEADERS
    except Exception as e:
        return Response(format(e), 500, content_type=CONTENT_TYPE)


if __name__ == '__main__':
    app.run(debug=True)
