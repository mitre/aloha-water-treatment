FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY simulator/ simulator/
COPY .env.example .
EXPOSE 5020 47808/udp 8090
ENTRYPOINT ["python", "-m", "simulator.plc"]
