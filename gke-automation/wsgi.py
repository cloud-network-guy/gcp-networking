import traceback
import json
from asyncio import run
from flask import Flask, request, render_template, Response
from main import main


app = Flask(__name__, static_url_path='/static')
app.config['JSON_SORT_KEYS'] = False


@app.route("/data")
def _data():

    try:
        data = run(main())
        return Response(json.dumps(data, indent=4), 200, content_type="application/json")
    except Exception as e:
        return Response(traceback.format_exc(), 500, content_type="text/plain")


@app.route("/")
@app.route("/index.html")
def _root():

    selected = {k: request.args.get(k, "") for k in ('network', 'region', 'subnet')}

    try:
        data = run(main())
        #return Response(json.dumps(data, indent=4), 200, content_type="application/json")

        # Check if a specific network has been selected
        if network := selected.get('network'):
            data['subnets'] = [s for s in data['subnets'] if s['network'] == network]

        # Check if a specific region has been selected
        if region := selected.get('region'):
            regions = [region]
        else:
            regions = set([s['region'] for s in data.get('subnets', [])])

        # Further filter subnets down to a specific region, if selected
        if region:
            data['subnets'] = [s for s in data['subnets'] if s['region'] == region]

        return render_template('index.html', data=data, selected=selected, regions=regions)

    except Exception as e:
        return Response(traceback.format_exc(), 500, content_type="text/plain")


if __name__ == '__main__':
    app.run(debug=True)
