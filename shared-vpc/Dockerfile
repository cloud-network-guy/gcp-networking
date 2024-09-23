FROM python:3.12.5-slim-bookworm
WORKDIR /tmp
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV APP_DIR=/opt/
ENV WEB_SERVER=hypercorn
ENV PORT=8080
COPY *.py $APP_DIR/
COPY *.toml $APP_DIR/
COPY *.json $APP_DIR/
ENTRYPOINT cd $APP_DIR && $WEB_SERVER -b 0.0.0.0:$PORT -w 1 --access-logfile '-' app:app
EXPOSE $PORT
