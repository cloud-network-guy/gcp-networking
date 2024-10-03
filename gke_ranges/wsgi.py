from flask import Flask, jsonify, request, Response
from asyncio import run
from main import *

app = Flask(__name__)

JSON_RESPONSE_HEADERS = {'Cache-Control': "no-cache, no-store"}


@app.route("/service-projects")
async def service_projects():
    try:

        parameters = await get_parameters(INPUT_FILE)
        host_project_id = parameters.get('host_project_id')
        access_token = await get_access_token(parameters.get('key_file'))
        _ = await get_service_projects(host_project_id, access_token)
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format(e), 500, content_type="text/plain")


@app.route("/service-projects/<project_id>")
async def _service_projects(project_id: str):
    try:

        parameters = await get_parameters(INPUT_FILE)
        host_project_id = parameters.get('host_project_id')
        network = parameters.get('network', "default")
        region = parameters.get('us-central1')
        access_token = await get_access_token(parameters.get('key_file'))

        _ = await get_subnetworks(host_project_id, network, access_token, region=region)
        subnetwork_ids = [subnet['id'] for subnet in _]
        tasks = [get_subnet_iam_bindings(subnet_id, access_token) for subnet_id in subnetwork_ids]
        _ = await asyncio.gather(*tasks)
        _ = dict(zip(subnetwork_ids, _))
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format(e), 500, content_type="text/plain")


@app.route("/subnets/<region>")
async def _subnets(region: str):
    try:

        parameters = await get_parameters(INPUT_FILE)
        host_project_id = parameters.get('host_project_id')
        access_token = await get_access_token(parameters.get('key_file'))
        network = parameters.get('network', "default")
        #region = parameters.get('region')
        _ = await get_subnetworks(host_project_id, network, access_token, region=region)
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format(e), 500, content_type="text/plain")


@app.route("/")
def _root():
    try:
        _ = run(main())
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format(e), 500, content_type="text/plain")


if __name__ == '__main__':
    app.run(debug=True)
