FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MUJOCO_GL=osmesa \
    LP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2 \
    PIP_NO_CACHE_DIR=1 \
    VIVACITY_DATABASE=/data/vivacity.sqlite3 \
    VIVACITY_HEADLESS_GEOMETRY=1 \
    VIVACITY_PHYSICS_TRIAL_WORKERS=2 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /app
RUN mkdir -p /data
RUN apt-get update && apt-get install -y --no-install-recommends libosmesa6 libgl1 && rm -rf /var/lib/apt/lists/*

COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt

COPY vivacity ./vivacity
COPY assets ./assets
COPY fixtures/imports ./fixtures/imports

EXPOSE 8000
VOLUME ["/data"]

CMD ["sh", "-c", "uvicorn vivacity.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
