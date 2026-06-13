# ViT-CORE-FORENSICS

**An enterprise-grade forensic deepfake detection workspace** built on a Dual-View Vision Transformer framework, delivering probabilistic, explainable assessments of media manipulation with full chain-of-custody audit logging.

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

ViT-CORE-FORENSICS is the production-deployment layer built on top of the [ViT-CORE](https://github.com/niiomar/ViT-CORE) training pipeline (an MSc Computer Science research project). It packages a Vision Transformer-based deepfake classifier into a full-stack forensic workspace: a FastAPI backend handling inference, attention-based explainability, audit logging, and rate limiting; and a Vite-built frontend providing an analyst-facing UI with session history and PDF report export.

The system is designed as a **screening aid for forensic analysts** — outputs are probabilistic, not verdicts, and are intended to support (not replace) human investigation.

---

## Architecture

### Dual-View Vision Transformer Pipeline

The classifier departs from standard CNN-based detection by using a self-attention-driven dual-view consistency architecture:

1. **Parallel Augmentation** — Each input face is split into two independently augmented views (`RaAug` and `DFDC_Selim`-style augmentations).
2. **Shared Encoder** — Both views are tokenized into 16×16 patches and passed through a shared `ViT-S/16` transformer encoder.
3. **Feature Embedding** — The resulting representations (`f1`, `f2`) are L2-normalized into embedding vectors (`f̃1`, `f̃2`).
4. **Consistency Constraint** — A Mean Squared Error consistency loss (`L_cons`) aligns the two embeddings before they are passed to a shared classification head.

### Inference Pipeline (this repository)

```
Upload → MTCNN face extraction → Face quality assessment
       → 4-view Test-Time Augmentation (orig / h-flip / center-crop / crop+flip)
       → ViT-S/16 forward pass → Confidence-weighted aggregation across frames
       → Attention Rollout heatmap (optional) → Audit log entry → JSON response
```

---

## Key Features

- **Attention Rollout Heatmaps** — Native QKV hooks on the final transformer block reconstruct the self-attention matrix directly (bypassing PyTorch's fused SDPA path, which breaks naive gradient-based hooks), producing a spatial map of which facial regions drove the verdict.
- **Conservative Frame Aggregation** — For video input, the reported face-quality metric is anchored to the *worst* quality observed across all sampled frames, not the first — a single blurry frame degrades the reported confidence for the whole clip.
- **Confidence-Weighted Logits** — Per-frame probabilities are aggregated with weights proportional to `|p - 0.5|`, so high-certainty frames dominate the final score and near-ambiguous frames are effectively discounted.
- **Forensic Audit Log** — Every analysis is recorded in an append-only SQLite log keyed by the SHA-256 hash of the input file, alongside verdict, confidence, model version, and timestamp — enabling "has this exact file been analysed before" lookups.
- **Batch Analysis** — `/api/v1/analyze/batch` accepts up to 50 files in a single request for evidence-set screening, with per-file error isolation.
- **Sliding-Window Rate Limiting** — Native request throttling protects inference compute from automated abuse.
- **PDF Report Export** — One-click forensic report generation (verdict, confidence, heatmap, explanation) via `jsPDF`.

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
│   ├── .env.example         # Backend config template
│   ├── weights/              # vitcore_best.pth goes here (download from Releases)
│   ├── static/               # Vite build output — generated, not tracked in git
│   └── tests/
│       └── test_smoke.py    # CPU smoke test for CI
│
├── frontend/
│   ├── src/
│   │   ├── app.js            # Entry point — UI logic, fetch calls, state
│   │   ├── styles.css
│   │   └── ...                # Modular components
│   ├── index.html
│   ├── .env.example          # Frontend config template (API key for dev builds)
│   ├── package.json
│   └── vite.config.js        # Build output → ../backend/static
│
├── .github/workflows/ci.yml  # Lint, compile-check, smoke test, frontend build
├── .gitignore
├── Dockerfile                 # Multi-stage: Vite build → Python runtime
├── docker-compose.yml
├── MODEL_CARD.md              # Training data, benchmarks, known limitations
└── LICENSE
```

> **Note on `static/`:** unlike earlier versions of this project, the Vite build output is **not** committed to git — it's a build artifact regenerated by `npm run build`. See [`.gitignore`](#configuration).

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- 8GB+ RAM (CUDA-enabled GPU recommended; CPU inference works but is slower)

### 1. Clone and set up the backend

```bash
git clone https://github.com/niiomar/VIT-CORE-FORENSICS.git
cd VIT-CORE-FORENSICS/backend

python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Download model weights

The trained checkpoint exceeds GitHub's file size limits and is distributed via Releases:

1. Go to the [Releases](https://github.com/niiomar/VIT-CORE-FORENSICS/releases) tab.
2. Download `vitcore_best.pth`.
3. Place it at `backend/weights/vitcore_best.pth`.

### 3. Configure environment variables

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` — at minimum confirm `MODEL_WEIGHTS_PATH=weights/vitcore_best.pth`. See [Configuration](#configuration) for all options.

### 4. Build the frontend

```bash
cd ../frontend
cp .env.example .env   # set VITE_API_KEY to match backend/.env if auth is enabled
npm install
npm run build
cd ..
```

This compiles the Vite project into `backend/static/`, which FastAPI serves directly.

### 5. Run the server

```bash
cd backend
uvicorn main:app --reload
```

Open **http://localhost:8000**.

---

## Configuration

All configuration is via environment variables, loaded from `.env` files (never committed — see `.gitignore`).

### `backend/.env`

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(unset)* | Shared secret for `X-API-KEY` header auth. If unset, the API is **unauthenticated** — fine for local dev, **not** for any exposed deployment. |
| `CORS_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Comma-separated list of allowed frontend origins. |
| `MODEL_WEIGHTS_PATH` | `vitcore_best.pth` | Path to the trained checkpoint, relative to `backend/`. |
| `AUDIT_DB_PATH` | `audit_log.db` | Path to the SQLite audit log. |

### `frontend/.env`

| Variable | Description |
|---|---|
| `VITE_API_KEY` | Baked into the JS bundle at build time. **Must match** `backend/.env`'s `API_KEY` exactly. Note: this is visible in the shipped bundle — see [Security & Deployment Notes](#security--deployment-notes). |

> ⚠️ After changing either `.env` file, you must `npm run build` again for `frontend/.env` changes to take effect (env vars are inlined at build time, not read at runtime).

---

## Docker Deployment

```bash
cp backend/.env.example backend/.env     # edit as needed
cp frontend/.env.example frontend/.env   # must match backend API_KEY

docker compose up --build
```

This runs a multi-stage build (Vite build → Python/FastAPI runtime) and serves the app on `http://localhost:8000`. Model weights and the audit database are mounted as volumes (`./weights`, `./data`) so they persist across container rebuilds.

To enable GPU inference, uncomment the `deploy.resources` block in `docker-compose.yml` (requires the NVIDIA Container Toolkit).

---

## API Reference

All endpoints (except `/health` and `/`) require the `X-API-KEY` header if `API_KEY` is set in `backend/.env`.

### `POST /api/v1/analyze`

Analyze a single image or video file.

| Param | Type | Description |
|---|---|---|
| `file` | form-data, required | Image (`jpg`, `png`, `webp`, `bmp`) or video (`mp4`, `avi`, `mov`, `mkv`, `webm`). |
| `explain` | query, bool, default `true` | Generate an attention rollout heatmap. |

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

Analyze up to 50 files in one request. `explain` defaults to `false` (heatmaps are expensive at scale).

```json
{
  "summary": { "total": 12, "fake": 2, "real": 9, "errors": 1 },
  "results": [ /* one object per file, same shape as /analyze, or {"filename": ..., "error": ...} */ ]
}
```

### `GET /api/v1/history?limit=50`

Returns the most recent audit log entries.

### `GET /api/v1/history/{file_sha256}`

Returns all past analyses for a given file hash — useful for verifying whether a specific file has been screened before.

### `GET /health`

Liveness check. Returns `{"status": "ok", "version": "..."}`.

---

## Model Card

Training data, benchmark results (FaceForensics++ / CelebDF / DFDC), and known limitations are documented in [`MODEL_CARD.md`](MODEL_CARD.md). **Read this before relying on model output for any decision-making context.**

---

## Security & Deployment Notes

- **The frontend API key is not a secret.** `VITE_API_KEY` is compiled into the publicly-served JS bundle. The `X-API-KEY` mechanism is a basic gate suitable for pilot/internal deployments, not a substitute for proper access control.
- **Recommended production setup:** place the application behind a reverse proxy (Nginx, Caddy, etc.) with IP allowlisting, mutual TLS, or basic auth, and treat `API_KEY` as a secondary layer rather than the primary control.
- **CORS** is locked to explicit origins via `CORS_ORIGINS` — do not set this to `*` in any deployment handling real evidence.
- **Audit log** (`audit_log.db`) contains file hashes and filenames of all analysed media. Treat it as sensitive data and back it up / rotate access according to your organization's evidence-handling policy.
- This system provides **probabilistic screening output only**. See the `disclaimer` field returned alongside `explanation_summary` in API responses, and [`MODEL_CARD.md`](MODEL_CARD.md) for known failure modes.

---

## Development

### Running tests

```bash
cd backend
pytest tests/ -v
```

### Frontend dev server (hot reload)

```bash
cd frontend
npm run dev
```

Runs on `http://localhost:5173` (or `3000`, per `vite.config.js`) with API requests proxied to `http://127.0.0.1:8000`. This is separate from the production build served by FastAPI — rebuild with `npm run build` to test the actual served bundle.

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR: backend compile-check + smoke test on CPU with untrained weights, and a frontend production build.

---

## Related Projects

- [ViT-CORE](https://github.com/niiomar/ViT-CORE) — the underlying training pipeline (dataset preparation, augmentations, training loop, evaluation) developed as part of an MSc Computer Science dissertation.

---

## License

Released under the [MIT License](LICENSE).
