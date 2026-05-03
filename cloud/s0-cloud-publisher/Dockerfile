FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY cloud/s0-cloud-publisher/requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY edge/modules/common/src ./src
COPY edge/modules/opcua-collector/src ./src
COPY cloud/s0-cloud-publisher/src ./src

CMD ["python", "-m", "s0_cloud_publisher.main"]
