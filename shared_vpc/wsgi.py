from flask import Flask, jsonify, request, Response
from asyncio import run
from main import main

app = Flask(__name__)


@app.route("/")
def _root():
    try:
        _ = run(main())
        return jsonify(_), {'Cache-Control': "no-cache, no-store"}
    except Exception as e:
        return Response(format(e), 500, content_type="text/plain")


if __name__ == '__main__':
    app.run(debug=True)
