# Stage 1: build the frontend
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
# VITE_API_KEY is baked into the bundle at build time
ARG VITE_API_KEY
ENV VITE_API_KEY=${VITE_API_KEY}
RUN npm run build

# Stage 2: backend runtime
FROM python:3.11-slim AS runtime

# OpenCV needs these system libs. Versions pinned for reproducible builds —
# update periodically with: apt-cache show <pkg> | grep Version
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0=2.74.6-2+deb12u5 \
    libsm6=2:1.2.3-1 \
    libxext6=2:1.3.4-1+b1 \
    libxrender1=1:0.9.10-1+b1 \
    libgl1=1.6.0-1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Built frontend assets land here, served by FastAPI's StaticFiles mount
COPY --from=frontend-build /app/frontend/dist ./static

# Model weights and audit DB are expected to be mounted as volumes
RUN mkdir -p /app/weights /app/data

# Run as a non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/sh --no-create-home appuser \
    && chown -R appuser:appgroup /app/data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
