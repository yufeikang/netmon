FROM python:3.12-slim

# Avoid tzdata interactive prompt
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        iputils-ping \
        iw \
        dnsutils \
        curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY net_monitor.py .
# Also COPY config.yaml if available
# COPY config.yaml .

ENTRYPOINT ["python", "/app/net_monitor.py"]