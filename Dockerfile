FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORTAL_HOST=0.0.0.0
ENV PORTAL_PORT=9000

WORKDIR /app

COPY portal.py portal_config.json ./
COPY assets ./assets

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORTAL_PORT\", \"9000\")}/health', timeout=3)"

CMD ["python", "portal.py"]
