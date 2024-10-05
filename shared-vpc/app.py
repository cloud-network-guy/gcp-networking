from traceback import format_exc
from quart import Quart, jsonify, request, Response
from main import *

app = Quart(__name__)
app.config['JSON_SORT_KEYS'] = False

JSON_RESPONSE_HEADERS = {'Cache-Control': "no-cache, no-store"}
PLAIN_CONTENT_TYPE = "text/plain"
FIELDS = ('key_file', 'host_project_id', 'network', 'region')


@app.route("/profiles")
async def _profiles():

    try:
        profiles = await get_profiles()
        _ = {k: v.get('network') for k, v in profiles.items() if k != 'global'}
        return jsonify(_, JSON_RESPONSE_HEADERS)
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/projects")
async def _projects():
    try:

        profiles = await get_profiles()
        global_profile = profiles.get('global', {})
        access_token = await get_access_token(global_profile.get('key_file'))
        projects = await get_projects(access_token)
        return jsonify(projects), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/service-projects")
async def _service_projects():
    try:

        profiles = await get_profiles()
        global_profile = profiles.get('global', {})
        access_token = await get_access_token(global_profile.get('key_file'))
        host_project_id = global_profile.get('host_project_id')
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

        profiles = await get_profiles()
        global_profile = profiles.get('global', {})
        access_token = await get_access_token(global_profile.get('key_file'))
        host_project_id = global_profile.get('host_project_id')
        _networks = await get_networks(host_project_id, access_token)
        return jsonify(_networks), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/service-projects/<profile>/<project_id>")
async def _service_project(profile: str, project_id: str):
    try:

        p = await get_profile(profile)
        _ = await get_subnetworks(p['host_project_id'], p['network'], p['access_token'], p['region'])
        service_project_information = {
            'host_project_id': p['host_project_id'],
            'subnets': _
        }
        return jsonify(service_project_information), JSON_RESPONSE_HEADERS
        tasks = [get_subnet_iam_bindings(subnet_id, access_token) for subnet_id in subnetwork_ids]
        _ = await asyncio.gather(*tasks)
        _ = dict(zip(subnetwork_ids, _))
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/subnets/<profile>/<region>")
async def _subnets(profile: str, region: str):
    try:

        p = await get_profile(profile)
        _ = await get_subnetworks(p['host_project_id'], p['network'], p['access_token'], p['region'])
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


@app.route("/")
async def _root():
    try:
        profiles = await get_profiles()
        _ = {k: v.get('network') for k, v in profiles.items() if k != 'global'}
        return jsonify(_), JSON_RESPONSE_HEADERS
    except Exception as e:
        return Response(format_exc(), 500, content_type=PLAIN_CONTENT_TYPE)


if __name__ == '__main__':
    app.run(debug=True)
