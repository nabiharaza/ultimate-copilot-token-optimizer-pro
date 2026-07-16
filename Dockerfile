FROM node:20-bookworm-slim AS frontend

WORKDIR /src
COPY TrimP/dashboard/frontend/package*.json ./TrimP/dashboard/frontend/
WORKDIR /src/TrimP/dashboard/frontend
RUN npm ci
COPY TrimP/dashboard/frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/trimp

# git: TrimPy shells out to it to attribute compressions to a repo/branch.
# curl: used by the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY TrimP ./TrimP
COPY byok_server.py ./
COPY --from=frontend /src/TrimP/dashboard/frontend/dist ./TrimP/dashboard/frontend/dist

RUN pip install --no-cache-dir .

# Run as a non-root user. Its home directory (/home/trimp) is where TrimPy
# keeps ~/.trimp/TrimP.db, matching the volume mount used below and in
# docker-compose.yml.
RUN useradd --create-home --home-dir /home/trimp --shell /usr/sbin/nologin trimp \
    && chown -R trimp:trimp /app
USER trimp

# Dashboard (web UI + REST API). The compression proxy (port 8765) is a
# separate process — see docker-compose.yml, or override CMD to run
# `python3 byok_server.py --host 0.0.0.0 --port 8765` in a second container
# from this same image.
EXPOSE 7432
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:7432/api/health || exit 1

CMD ["trimp", "dashboard", "--mode", "web", "--host", "0.0.0.0", "--port", "7432", "--no-browser"]
