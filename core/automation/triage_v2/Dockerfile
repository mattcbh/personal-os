FROM python:3.12-slim

WORKDIR /app

COPY src /app/src
ENV PYTHONPATH=/app/src
ENV TRIAGE_V2_STATE_DIR=/tmp/email-triage-v2

EXPOSE 8080

CMD ["python3", "-m", "triage_v2", "serve-api", "--host", "0.0.0.0", "--port", "8080"]
