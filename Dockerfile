# Avighna BOQ API — Render / any Docker host
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONWARNINGS=ignore \
    DATA_DIR=/data STORAGE_BACKEND=supabase

# LibreDWG (dwg2dxf) for DWG -> DXF, plus fonts/libs PyMuPDF and matplotlib need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libredwg-tools ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && dwg2dxf --version || true

WORKDIR /app
# build context is the repository root (see render.yaml) so database/ can be copied too
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY database /database
ENV DATABASE_DIR=/database

RUN mkdir -p /data && useradd -m appuser && chown -R appuser /app /data
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://127.0.0.1:${PORT:-8000}/healthz || exit 1
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
