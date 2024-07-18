FROM python:3.12-alpine
WORKDIR /opt
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
ENV APP_DIR=/opt
ENV NUM_WORKERS=1
COPY main.py $APP_DIR
COPY wsgi.py $APP_DIR
COPY settings.yaml $APP_DIR
COPY *.json $APP_DIR/
ENTRYPOINT cd $APP_DIR && gunicorn -b 0.0.0.0:$PORT -w $NUM_WORKERS --access-logfile '-' wsgi:app
EXPOSE $PORT