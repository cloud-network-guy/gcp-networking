FROM python:3.14-alpine
WORKDIR /tmp
RUN pip install --upgrade pip
COPY ./pyproject.toml ./
RUN pip install . --break-system-packages
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
ENTRYPOINT cd $APP_DIR && uvicorn $APP_APP --host 0.0.0.0 --port $PORT
EXPOSE $PORT

