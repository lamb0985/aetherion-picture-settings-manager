FROM python:3.12-slim-trixie
WORKDIR /app
RUN printf 'deb http://deb.debian.org/debian trixie-backports main contrib\n' > /etc/apt/sources.list.d/scrcpy-backports.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends adb passwd tzdata xvfb x11vnc novnc curl ca-certificates \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends -t trixie-backports scrcpy \
    && scrcpy --version \
    && test -f /usr/share/novnc/core/rfb.js \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /config /backups /logs \
    && chown 1000:1000 /config /backups /logs \
    && chmod 775 /config /backups /logs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py schema.py device_manager.py scanner.py cli_transport.py remote.py bulk.py ./
COPY entrypoint.py /app/entrypoint.py
COPY templates/ templates/
COPY static/ static/
ENV TZ=America/New_York HOME=/config CONFIG_DIR=/config PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN python -c "from app import app; assert app.test_client().get('/health').status_code == 200"
EXPOSE 5055
ENTRYPOINT ["python", "/app/entrypoint.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:5055", "--workers", "1", "--threads", "4", "app:app"]
