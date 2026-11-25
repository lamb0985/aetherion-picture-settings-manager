FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends adb tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /config /backups /logs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py schema.py device_manager.py scanner.py ./
COPY templates/ templates/
COPY static/ static/
ENV TZ=America/New_York HOME=/config CONFIG_DIR=/config PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 5055
CMD ["gunicorn", "--bind", "0.0.0.0:5055", "--workers", "1", "--threads", "4", "app:app"]
