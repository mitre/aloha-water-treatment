FROM python:3.13-alpine
LABEL authors="MITRE"

WORKDIR /app

COPY requirements.txt requirements.txt
COPY runenv.py run.py
COPY aloha/constants.py aloha/constants.py
COPY aloha/plc aloha/plc
COPY aloha/hmi aloha/hmi
COPY aloha/modbus aloha/modbus
COPY aloha/bacnet aloha/bacnet

RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt; chmod +x /app/run.py

ENTRYPOINT ["python3", "/app/run.py"]
