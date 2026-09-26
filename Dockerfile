FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM docker:29-cli AS dockercli

FROM python:3.12-slim-bookworm AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_URL=sqlite:////data/codearena-v3.db
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && groupadd --gid 10001 codearena && useradd --uid 10001 --gid 10001 --no-create-home codearena && mkdir /data && chown 10001:10001 /data
COPY backend/ ./
COPY --from=frontend /frontend/dist /app/frontend/dist
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]

FROM api AS worker
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
CMD ["python", "-m", "judge.worker"]
