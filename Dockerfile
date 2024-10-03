#FROM python:3.12-slim-bookworm
FROM python:3.12-alpine
WORKDIR /tmp
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
ENV APP_DIR=/var/local
ENV APP_APP=app:app
COPY *.py $APP_DIR
COPY *.toml $APP_DIR
COPY settings.yaml $APP_DIR
COPY static/ $APP_DIR/static/
COPY templates/ $APP_DIR/templates/
ENTRYPOINT cd $APP_DIR && hypercorn -b 0.0.0.0:$PORT -w 1 --access-logfile '-' $APP_APP
EXPOSE $PORT

