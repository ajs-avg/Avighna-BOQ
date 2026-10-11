# Avighna BOQ API — Render / any Docker host. Build context = repository root.

# ---- stage 1: build LibreDWG 0.13.4 (dwg2dxf) from source, statically linked ---------------
FROM python:3.12-slim AS libredwg
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config curl xz-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ftp.gnu.org/gnu/libredwg/libredwg-0.13.4.tar.xz | tar -xJ -C /tmp \
    && cd /tmp/libredwg-0.13.4 \
    && ./configure --prefix=/usr/local --disable-bindings --disable-python --disable-docs \
                   --disable-dependency-tracking --disable-shared --enable-static \
    && make -j"$(nproc)" CFLAGS="-O2 -Wno-error" \
    && make install-strip CFLAGS="-O2 -Wno-error" \
    && /usr/local/bin/dwg2dxf --version

# ---- stage 2: runtime ---------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONWARNINGS=ignore \
    DATA_DIR=/data DATABASE_DIR=/database STORAGE_BACKEND=supabase LIBREDWG_BIN=/usr/local/bin/dwg2dxf
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=libredwg /usr/local/bin/dwg2dxf /usr/local/bin/dwg2dxf
RUN /usr/local/bin/dwg2dxf --version

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY database /database

RUN mkdir -p /data && useradd -m appuser && chown -R appuser /app /data
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://127.0.0.1:${PORT:-8000}/healthz || exit 1
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
