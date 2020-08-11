FROM python:3-alpine

WORKDIR /app

RUN apk add gcc musl-dev libffi-dev openssl-dev python3-dev
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p ./telefly_iii
COPY telefly_iii/*.py ./telefly_iii/

ENV TELEFLY_III_CONFIG=/config/telefly-iii.ini

CMD [ "python", "-m", "telefly_iii" ]
VOLUME [ "/config" ]
