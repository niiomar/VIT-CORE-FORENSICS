# ViT-CORE-FORENSICS

**A full-stack deepfake forensic analysis platform** built on a Dual-View Vision Transformer framework, delivering probabilistic, explainable assessments of media manipulation with forensic audit logging.

[![CI](https://github.com/niiomar/VIT-CORE-FORENSICS/actions/workflows/ci.yml/badge.svg)](https://github.com/niiomar/VIT-CORE-FORENSICS/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Docker Deployment](#docker-deployment)
- [API Reference](#api-reference)
- [Model Card](#model-card)
- [Security & Deployment Notes](#security--deployment-notes)
- [Development](#development)
- [License](#license)

---

## Overview

ViT-CORE-FORENSICS is the production-deployment layer built on top of the [ViT-CORE](https://github.com/niiomar/ViT-CORE) training pipeline — an MSc Computer Science research project. It packages a Vision Transformer-based deepfake classifier into a full-stack forensic workspace: a FastAPI backend handling inference, attention-based explainability, audit logging, and rate limiting; and a Vite-built frontend providing an analyst-facing UI with session history and PDF report export.

The system is designed as a **screening aid for forensic analysts**. Outputs are probabilistic assessments, not definitive verdicts, and are intended to support — not replace — human investigation.

---

## Architecture

### Dual-View Vision Transformer Pipeline

The classifier departs from standard CNN-based detection by using a self-attention-driven dual-view consistency architecture:

1. **Parallel Augmentation** — Each input face is split into two independently augmented views (`RaAug` and `DFDC_Selim`-style augmentations).
2. **Shared Encoder** — Both views are tokenized into 16×16 patches and passed through a shared `ViT-S/16` transformer encoder.
3. **Feature Embedding** — The resulting representations (`f1`, `f2`) are L2-normalized into embedding vectors (`f̃1`, `f̃2`).
4. **Consistency Constraint** — A Mean Squared Error consistency loss (`L_cons`) aligns the two embeddings before they are passed to a shared classification head.

### Inference Pipeline

```
Upload → MTCNN face extraction → Face quality assessment (3-tier: Poor / Fair / High)
       → 4-view Test-Time Augmentation (orig / h-flip / center-crop / crop+flip)
       → ViT-S/16 forward pass → Confidence-weighted aggregation across frames
       → Attention Rollout heatmap (optional) → Audit log entry → JSON response
```

---

## Key Features

- **Attention Rollout Heatmaps** — Native QKV hooks on the final transformer block reconstruct the self-attention matrix directly, bypassing PyTorch's fused SDPA path which breaks naive gradient-based hooks. Produces a spatial map of which facial regions drove the classification.
- **Conservative Frame Aggregation** — For video input, the reported face-quality metric is anchored to the *worst* quality observed across all sampled frames — a single blurry frame degrades the reported confidence for the whole clip.
- **Confidence-Weighted Logits** — Per-frame probabilities are aggregated with weights proportional to `|p - 0.5|`, so high-certainty frames dominate the final score and near-ambiguous frames are discounted.
- **Forensic Audit Log** — Every analysis is recorded in an append-only SQLite log keyed by the SHA-256 hash of the input file, alongside verdict, confidence, model version, and timestamp — supporting "has this exact file been analysed before" lookups.
- **Batch Analysis** — `/api/v1/analyze/batch` accepts up to 50 files per request for evidence-set screening, with per-file error isolation.
- **Sliding-Window Rate Limiting** — Native request throttling protects inference compute from automated abuse.
- **PDF Report Export** — One-click forensic report generation (verdict, confidence, heatmap) via `jsPDF`.

---

## Project Structure

```
ViT-CORE-FORENSICS/
├── backend/
│   ├── main.py              # FastAPI app: routes, rate limiting, CORS, lifespan
│   ├── model.py             # PyTorch inference, MTCNN, TTA, attention rollout
│   ├── auth.py              # API key dependency (optional, env-gated)
│   ├── audit.py             # SQLite forensic audit log
│   ├── requirements.txt     # Python dependencies (NumPy < 2.0 locked)
│   ├── .env.example         # Backend config template — copy to .env
│   ├── weights/             # Place vitcore_best.pth here (download from Releases)
│   ├── static/              # Vite build output — generated, not tracked in git
│   └── tests/
│       └── test_smoke.py    # CPU smoke test for CI
│
├── frontend/
│   ├── src/
│   │   ├── app.js           # Entry point — UI logic, fetch calls, state
│   │   ├── styles.css
│   │   └── utils/           # api.js, report.js
│   ├── index.html
│   ├── .env.example         # Frontend config template — copy to .env
│   ├── package.json
│   └── vite.config.js       # Build output → ../backend/static
│
├── .github/workflows/ci.yml  # Compile-check, smoke test, frontend build
├── .gitignore
├── CONTRIBUTING.md
├── Dockerfile                # Multi-stage: Vite build → Python runtime
├── docker-compose.yml
├── MODEL_CARD.md             # Training data, benchmarks, known limitations
├── SECURITY.md
└── LICENSE
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- 8GB+ RAM (CUDA-enabled GPU recommended; CPU inference works but is slower)

### 1. Clone the repository

```bash
git clone https://github.com/niiomar/VIT-CORE-FORENSICS.git
cd VIT-CORE-FORENSICS
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Download model weights

The trained checkpoint exceeds GitHub's file size limits and is distributed via Releases:

1. Go to the [Releases](https://github.com/niiomar/VIT-CORE-FORENSICS/releases) tab.
2. Download `vitcore_best.pth`.
3. Place it at `backend/weights/vitcore_best.pth`.

### 4. Configure environment variables

```bash
# from backend/
cp .env.example .env
# Edit .env — set MODEL_WEIGHTS_PATH=weights/vitcore_best.pth and API_KEY

# from frontend/
cd ../frontend
cp .env.example .env
# Set VITE_API_KEY to match backend/.env API_KEY
```

### 5. Build the frontend

```bash
# from frontend/
npm install
npm run build
```

This compiles the Vite project into `backend/static/`, which FastAPI serves directly.

### 6. Run the server

```bash
cd ../backend
uvicorn main:app --reload
```

Open **http://localhost:8000**.

---

## Configuration

All configuration is via environment variables loaded from `.env` files. These are never committed — see `.gitignore`.

### `backend/.env`

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(unset)* | Shared secret for `X-API-KEY` header auth. If unset, the API is unauthenticated — acceptable for local use, not for any exposed deployment. |
| `CORS_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Comma-separated allowed frontend origins. |
| `MODEL_WEIGHTS_PATH` | `vitcore_best.pth` | Path to the trained checkpoint, relative to `backend/`. |
| `AUDIT_DB_PATH` | `audit_log.db` | Path to the SQLite audit log file. |

### `frontend/.env`

| Variable | Description |
|---|---|
| `VITE_API_KEY` | Baked into the JS bundle at build time. Must match `API_KEY` in `backend/.env`. See [Security & Deployment Notes](#security--deployment-notes) for caveats. |

> ⚠️ Changes to `frontend/.env` only take effect after `npm run build`. The env vars are inlined at build time, not read at runtime.

---

## Docker Deployment

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Edit both files before building

docker compose up --build
```

This runs a multi-stage build (Vite → Python/FastAPI runtime) and serves the application on **http://localhost:8000**. Model weights and the audit database are mounted as volumes so they persist across container rebuilds.

To enable GPU inference, uncomment the `deploy.resources` block in `docker-compose.yml` (requires the NVIDIA Container Toolkit).

---

## API Reference

All endpoints except `/health` and `/` require the `X-API-KEY` header when `API_KEY` is set.

### `POST /api/v1/analyze`

Analyze a single image or video file.

| Parameter | Type | Description |
|---|---|---|
| `file` | form-data, required | Image (`jpg`, `png`, `webp`, `bmp`) or video (`mp4`, `avi`, `mov`, `mkv`, `webm`). |
| `explain` | query bool, default `true` | Generate attention rollout heatmap. |

**Response:**

```json
{
  "verdict": "REAL",
  "confidence": 51.5,
  "probability": 0.485,
  "processing_time_sec": 0.4,
  "face_detected": true,
  "face_quality": "Poor",
  "type": "jpg",
  "frames_analyzed": 1,
  "is_low_confidence": true,
  "explainability_maps": ["<base64 JPEG>"],
  "filename": "evidence.jpg",
  "file_sha256": "..."
}
```

### `POST /api/v1/analyze/batch`

Analyze up to 50 files in one request. `explain` defaults to `false`.

```json
{
  "summary": { "total": 12, "fake": 2, "real": 9, "errors": 1 },
  "results": [{ "..." }]
}
```

### `GET /api/v1/history?limit=50`

Returns the most recent audit log entries.

### `GET /api/v1/history/{file_sha256}`

Returns all past analyses for a specific file hash.

### `GET /health`

Liveness check. Returns `{"status": "ok", "version": "2.0.0"}`.

---

## Model Card

Training data, benchmark results (FaceForensics++ / CelebDF / DFDC), and known limitations are documented in [`MODEL_CARD.md`](MODEL_CARD.md). **Read this before relying on model output for any decision-making context.**

---

## Security & Deployment Notes

- **The frontend API key is not a secret.** `VITE_API_KEY` is compiled into the publicly-served JS bundle and is visible to anyone who inspects the source. The `X-API-KEY` mechanism is a basic access gate suitable for internal or pilot deployments — it is not a substitute for proper access control.
- **Recommended production setup:** deploy behind a reverse proxy (Nginx, Caddy) with IP allowlisting or mutual TLS. Treat `API_KEY` as a secondary layer, not the primary security boundary.
- **CORS** is locked to explicit origins via `CORS_ORIGINS`. Do not set this to `*` in any deployment handling real evidence.
- **Audit log** (`audit_log.db`) records file hashes and filenames of all analysed media. Treat it as sensitive operational data — back it up and restrict access per your organization's evidence-handling policy.
- Results are **probabilistic screening outputs only**. They should be treated as one input to a broader investigation, not as standalone conclusions.

---

## Development

### Running in development mode (two terminals)

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn main:app --reload
```

**Terminal 2 — Frontend (hot reload):**
```bash
cd frontend
npm run dev
```

Frontend runs on **http://localhost:5173** with API requests proxied to `http://127.0.0.1:8000`.

### Running as a single app (production mode)

```bash
# Step 1: build the frontend
cd frontend
npm run build

# Step 2: serve everything through FastAPI
cd ../backend
uvicorn main:app --reload
```

Open **http://localhost:8000**.

### Running tests

```bash
cd backend
pytest tests/ -v
```

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request: backend compile-check, CPU smoke test with untrained weights, and a frontend production build.

---

## Related Projects

- [ViT-CORE](https://github.com/niiomar/ViT-CORE) — the underlying training pipeline (dual-view architecture, augmentations, loss functions, evaluation) developed as part of an MSc Computer Science dissertation.

---

## License

Released under the [MIT License](LICENSE).
