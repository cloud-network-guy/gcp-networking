FROM python:3.12.5-slim-bookworm
WORKDIR /tmp
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV APP_DIR=/tmp
COPY *.py $APP_DIR
COPY *.yaml ./
COPY *.json $APP_DIR
ENTRYPOINT ["python3", "main.py"]

