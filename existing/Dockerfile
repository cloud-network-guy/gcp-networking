FROM python:3.12.5-slim-bookworm
WORKDIR /tmp
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
ENV APP_DIR=/tmp
COPY *.py ./
COPY *.yaml ./
COPY *.toml ./
COPY *.json ./
ENTRYPOINT gunicorn -b 0.0.0.0:$PORT -w 1 --access-logfile '-' wsgi:app
EXPOSE $PORT
