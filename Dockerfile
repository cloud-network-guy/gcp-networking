FROM python:3.12-alpine
WORKDIR /tmp
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
ENV APP_DIR=/opt/apps/gcp-networking
ENV APP_APP=app:app
RUN mkdir -p $APP_DIR
RUN mkdir -p /opt/private/gcp_keys
COPY *.py $APP_DIR/
COPY *.toml $APP_DIR/
COPY settings.yaml $APP_DIR/
COPY static/ $APP_DIR/static/
COPY templates/ $APP_DIR/templates/
COPY *.json /opt/private/gcp_keys/
#CMD ["pip", "list"]
ENTRYPOINT cd $APP_DIR && uvicorn $APP_APP --app-dir $APP_DIR --host 0.0.0.0 --port $PORT
EXPOSE $PORT

