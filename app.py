#!/usr/bin/env python3

from traceback import format_exc
#from quart import Quart, jsonify, render_template, request, Response, session
from fastapi import FastAPI, Request, Response, Form
from fastapi.responses import JSONResponse, PlainTextResponse
#from fastapi.encoders import jsonable_encoder
#from typing import Optional

from file_utils import get_version, get_settings, get_profile, apply_filter
from gcp_utils import *

RESPONSE_HEADERS = {'Cache-Control': "no-cache, no-store", 'Pragma': "no-cache"}
PLAIN_CONTENT_TYPE = "text/plain"

#app = Quart(__name__, static_url_path='/static')
app = FastAPI()


@app.get("/version")
async def _version(request: Request):

    try:
        _ = await get_version(request)
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/profiles")
async def _profiles():

    try:
        settings = await get_settings()
        profiles = settings.get('profiles')
        return JSONResponse(profiles, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/projects")
async def _projects():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        projects = await get_projects(access_token)
        return JSONResponse([item.__dict__ for item in projects], headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/service-projects")
async def _service_projects():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        host_project_id = settings.get('host_project_id')
        service_projects = await get_service_projects(host_project_id, access_token)
        options = request.args
        if _profile := options.get('profile'):
            _ = await get_profile(settings, _profile)
            if folder_id := _.get('folder_id'):
                parent_filter = f"parent.type:folder parent.id:{folder_id}"
                folder_projects = await get_projects(access_token, parent_filter=parent_filter)
                folder_project_ids = [p.id for p in folder_projects]
                service_projects = [sp for sp in service_projects if sp in folder_project_ids]
        _ = {
            'host_project_id': host_project_id,
            'service_projects': service_projects,
        }
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/networks")
async def _networks():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        host_project_id = settings.get('host_project_id')
        networks = await get_networks(host_project_id, access_token)
        networks = await apply_filter(networks, settings, request.args)
        return JSONResponse([item.__dict__ for item in networks], headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/subnets")
async def _subnets():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        host_project_id = settings.get('host_project_id')
        options = request.args
        regions = [options.get('region')] if 'region' in options else options.get('regions')
        subnets = await get_subnets(host_project_id, access_token, regions=regions)
        subnets = await apply_filter(subnets, settings, options)
        if network_name := options.get('network'):
            subnets = [s for s in subnets if s.network_name == network_name]
        tasks = [s.get_bindings(access_token) for s in subnets]
        _ = await gather(*tasks)
        projects = await get_projects(access_token)
        for s in subnets:
            if s.members:
                s.attached_projects = []
                for p in projects:
                    if f"serviceAccount:{p.number}-compute@developer.gserviceaccount.com" in s.members:
                        s.attached_projects.append(p.id)
                    #print(s)
        return JSONResponse([s.__dict__ for s in subnets], headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/rancid")
async def _rancid():

    from rancid import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/addresses")
async def _addresses():

    from ip_addresses import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/check-quotas")
async def _check_quotas():

    from check_quotas import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/check-ssl-certs")
async def _check_ssl_certs():

    from check_ssl_certs import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/list-access-configs")
async def _list_access_configs():

    from list_access_configs import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/ip-addresses")
async def _ip_addresses():

    from ip_addresses import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/empty-subnets")
async def _empty_subnets():

    from get_empty_subnets import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/gke-clusters")
async def _gke_clusters():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        projects = await get_projects(access_token)
        if host_project_id := settings.get('host_project_id'):
            service_projects = await get_service_projects(host_project_id, access_token)
            projects = [p for p in projects if p.id in service_projects]
        tasks = [p.get_gke_clusters(access_token) for p in projects]
        _ = await gather(*tasks)
        gke_clusters = []
        for p in projects:
            gke_clusters.extend(p.gke_clusters)
        _ = await apply_filter(gke_clusters, settings, request.args)
        return JSONResponse([item.__dict__ for item in _], headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/instances")
async def _instances():

    try:
        settings = await get_settings()
        key_file = settings.get('key_file')
        access_token = await get_access_token(key_file)
        projects = await get_projects(access_token)
        if host_project_id := settings.get('host_project_id'):
            service_projects = await get_service_projects(host_project_id, access_token)
            projects = [p for p in projects if p.id in service_projects]
        tasks = [p.get_instances(access_token) for p in projects]
        _ = await gather(*tasks)
        instances = []
        for p in projects:
            instances.extend(p.instances)
        instance_nics = []
        for instance in instances:
            instance_nics.extend(instance.nics)
        instance_nics = await apply_filter(instance_nics, settings, request.args)
        subnet_keys = [nic.subnet_key for nic in instance_nics]
        used_subnets = {}
        for sk in subnet_keys:
            used_subnets[sk] = list(set([nic.project_id for nic in instance_nics if nic.subnet_key == sk]))
        return JSONResponse(used_subnets, headers=RESPONSE_HEADERS)
        #return return JSONResponse([item.__dict__ for item in instance_nics]), RESPONSE_HEADERS
        
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/recent-firewall-rules")
async def _recent_firewall_rules():

    from recent_firewall_rules import main

    try:
        _ = await main()
        return JSONResponse(content=_, headers=RESPONSE_HEADERS)
    except Exception as e:
        return PlainTextResponse(content=format_exc(), status_code=500)


@app.get("/")
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
        return PlainTextResponse(content=format_exc(), status_code=500)


if __name__ == '__main__':

    import uvicorn

    #app.run(debug=True)
    uvicorn.run(app, host='127.0.0.1', port=8000, reload=False, reload_delay=3)
