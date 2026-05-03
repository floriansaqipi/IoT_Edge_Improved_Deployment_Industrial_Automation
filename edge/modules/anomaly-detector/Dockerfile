FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY anomaly-detector/requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY common/src ./src
COPY anomaly-detector/src ./src

CMD ["python", "-m", "anomaly_detector.main"]
