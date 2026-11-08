# Single-image build: React frontend + FastAPI backend on one URL.
# Used by render.yaml (one-click deploy) and works on any Docker host:
#   docker build -t splitsync . && docker run -p 8000:8000 splitsync

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist ./static
RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app
ENV STATIC_DIR=/app/static \
    DATABASE_URL=sqlite:////data/splitsync.db \
    PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/api/health')"
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
