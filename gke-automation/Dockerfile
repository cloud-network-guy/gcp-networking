FROM python:3.12-alpine
WORKDIR /opt
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
ENV APP_DIR=/opt
ENV NUM_WORKERS=1
ENV GOOGLE_APPLICATION_CREDENTIALS=/opt/application_default_credentials.json
COPY main.py $APP_DIR
COPY wsgi.py $APP_DIR
COPY settings.yaml $APP_DIR
COPY *.json $APP_DIR/
COPY templates/ $APP_DIR/templates/
ENTRYPOINT cd $APP_DIR && gunicorn -b 0.0.0.0:$PORT -w $NUM_WORKERS --access-logfile '-' wsgi:app
EXPOSE $PORT