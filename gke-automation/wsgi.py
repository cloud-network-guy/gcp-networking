import traceback
import json
from asyncio import run
from flask import Flask, Response
from main import main


app = Flask(__name__, static_url_path='/static')
app.config['JSON_SORT_KEYS'] = False


@app.route("/")
@app.route("/index.html")
def _root():
    try:
        _ = run(main())
        return Response(json.dumps(_, indent=4), 200, content_type="application/json")
    except Exception as e:
        return Response(traceback.format_exc(), 500, content_type="text/plain")


if __name__ == '__main__':
    app.run()
