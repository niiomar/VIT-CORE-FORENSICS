# ── Stage 1: build the frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
# VITE_API_KEY is baked into the bundle at build time
ARG VITE_API_KEY
ENV VITE_API_KEY=${VITE_API_KEY}
RUN npm run build

# ── Stage 2: backend runtime ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# OpenCV needs these system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Built frontend assets land here, served by FastAPI's StaticFiles mount
COPY --from=frontend-build /app/frontend/dist ./static

# Model weights and audit DB are expected to be mounted as volumes
RUN mkdir -p /app/weights /app/data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
