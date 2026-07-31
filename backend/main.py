from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
loaded = load_dotenv(dotenv_path=env_path)
print(f"[Config] .env loaded: {loaded} (path: {env_path})")

import asyncio
import logging
import time
import os
import cv2
import tempfile
from contextlib import asynccontextmanager
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from model import analyze_all_faces, get_models, get_status
from auth import verify_api_key
from ratelimit import enforce_rate_limit
from version import MODEL_VERSION
from observability import (
    configure_logging, ObservabilityMiddleware, metrics_response, BATCH_SIZE,
)
import audit

configure_logging()
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.bmp')

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing neural weights...")
    get_models()
    yield
    logger.info("Shutting down.")

app = FastAPI(title="ViT-CORE-FORENSICS API", version=MODEL_VERSION, lifespan=lifespan)

# Security: Explicit origins for local Vite development and cross-port traffic
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

# Merge any additional origins from .env
env_cors = os.getenv("CORS_ORIGINS", "")
if env_cors:
    CORS_ORIGINS.extend([o.strip() for o in env_cors.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # Allows OPTIONS pre-flight checks required by browsers
    allow_headers=["*"],  # Allows custom headers like X-API-KEY
)

# Assigns/propagates a request ID (X-Request-ID) for log correlation and
# records Prometheus metrics for every request. Added last so it's the
# outermost middleware and its timing captures CORS handling too.
app.add_middleware(ObservabilityMiddleware)

# Frame extraction
#
# This does purely blocking work (tempfile I/O, cv2 decode) with no real
# await points, so it — and _run_analysis_sync below — run off the event
# loop via asyncio.to_thread. That's what lets analyze_batch process
# multiple files concurrently instead of one at a time, and stops a single
# slow analysis from stalling every other in-flight request.
def extract_frames_to_pil(filename: str, content: bytes, num_frames=10):
    """Safely extracts frames using dynamic file suffix and converts to PIL Images."""
    file_suffix = Path(filename).suffix.lower()
    if not file_suffix:
        file_suffix = ".mp4"

    frames = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames <= 0:  # Static image fallback
            cap.release()
            img = cv2.imread(tmp_path)
            if img is not None:
                frames.append(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            return frames

        step = max(1, total_frames // num_frames)
        for i in range(num_frames):
            target = i * step
            if target >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            ret, frame = cap.read()
            if ret and frame is not None:
                frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        cap.release()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return frames

# Core analysis (shared by single + batch endpoints). Synchronous — always
# invoked via asyncio.to_thread, never awaited directly.
def _run_analysis_sync(filename: str, content: bytes, explain: bool) -> dict:
    start_time = time.time()
    filename_lower = (filename or "").lower()

    if not filename_lower.endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(status_code=400, detail=f"Unsupported media format: {filename}")

    frames = extract_frames_to_pil(filename, content)
    if not frames:
        raise HTTPException(status_code=400, detail=f"Could not extract frames from {filename}.")

    frame_data = []
    heatmaps = []
    max_faces_in_a_frame = 0
    single_image_faces = None  # populated only when len(frames) == 1

    for frame in frames:
        # Every face in the frame is detected and scored independently;
        # the primary (largest) face drives the existing frame-level
        # aggregation below, unchanged from the single-face behavior this
        # was built around. There's no face-identity tracking across
        # frames, so a full per-face breakdown is only trustworthy for a
        # single image — see the `faces` field built after this loop.
        faces = analyze_all_faces(frame, generate_explainability=explain)
        max_faces_in_a_frame = max(max_faces_in_a_frame, len(faces))

        if not faces:
            frame_data.append({"probability": None, "face_detected": False, "quality": {"valid": False, "status": "N/A", "blur": 0}})
            continue

        primary = faces[0]
        frame_data.append({
            "probability": primary["probability"],
            "face_detected": True,
            "quality": primary["quality"],
        })
        # visuals is a dict of base64-encoded images
        # ({"heatmap", "patches", "attention"}); the API only surfaces the
        # blended JET heatmap, matching the documented response shape.
        if primary["visuals"].get("heatmap"):
            heatmaps.append(primary["visuals"]["heatmap"])

        # A single-image upload has no cross-frame identity ambiguity, so
        # every detected face can be safely scored and reported on its own.
        if len(frames) == 1:
            single_image_faces = faces

    # Filter out None probabilities (where MTCNN bypassed the ViT)
    probs = [f["probability"] for f in frame_data if f["probability"] is not None]
    
    faces_found = any(f["face_detected"] for f in frame_data)

    # FIX: Handle Out-Of-Domain Bypass
    if not faces_found or len(probs) == 0:
        agg_prob = None
        is_fake = False
        final_quality_status = "N/A"
        disposition_override = "No human subjects detected by MTCNN. Neural inference bypassed."
    else:
        weights = [abs(p - 0.5) for p in probs]
        weight_sum = sum(weights)

        agg_prob = (sum(p * w for p, w in zip(probs, weights)) / weight_sum
                    if weight_sum > 0 else sum(probs) / len(probs))
        is_fake = agg_prob >= 0.5
        disposition_override = None

        # Conservative aggregation: report the WORST quality seen across all
        # frames where a face was detected
        quality_statuses = [f["quality"]["status"] for f in frame_data if f["face_detected"]]
        if quality_statuses:
            from model import QUALITY_RANK
            worst_status = min(quality_statuses, key=lambda s: QUALITY_RANK.get(s, 0))
            final_quality_status = worst_status
        else:
            final_quality_status = "N/A"

    result = {
        "verdict": "UNKNOWN" if agg_prob is None else ("FAKE" if is_fake else "REAL"),
        "confidence": None if agg_prob is None else round((agg_prob if is_fake else 1 - agg_prob) * 100, 1),
        "probability": None if agg_prob is None else round(float(agg_prob), 4),
        "processing_time_sec": round(time.time() - start_time, 2),
        "face_detected": faces_found,
        "face_quality": final_quality_status,
        "type": filename_lower.split('.')[-1],
        "frames_analyzed": len(probs),
        "is_low_confidence": False if agg_prob is None else (0.4 < agg_prob < 0.6),
        "explainability_maps": heatmaps,
        "filename": filename,
        "multiple_faces_detected": max_faces_in_a_frame > 1,
    }

    if single_image_faces is not None and len(single_image_faces) > 1:
        # Independent per-face verdicts — safe for a single image since
        # there's no cross-frame identity to conflate. The top-level
        # verdict above still reflects only the primary (largest) face.
        result["faces"] = [
            {
                "probability": round(f["probability"], 4),
                "verdict": "FAKE" if f["probability"] >= 0.5 else "REAL",
                "confidence": round((f["probability"] if f["probability"] >= 0.5 else 1 - f["probability"]) * 100, 1),
                "face_quality": f["quality"]["status"],
            }
            for f in single_image_faces
        ]
        disposition_override = (
            f"{len(single_image_faces)} faces detected in this image — see 'faces' for "
            "independent per-face verdicts. The top-level verdict reflects the primary "
            "(largest) face only."
        )
    elif max_faces_in_a_frame > 1:
        # Video: we deliberately don't attempt to aggregate multiple faces
        # across frames without identity tracking — doing so would risk
        # silently blending different people's probabilities into one
        # misleading number. Surface the limitation instead.
        disposition_override = (
            f"Multiple faces detected in at least one frame (up to {max_faces_in_a_frame}). "
            "The verdict aggregates only the primary (largest) face per frame — this may not "
            "represent every subject in the video. Manual review recommended for multi-subject footage."
        )

    # Pass the disposition override up if we bypassed, or if a multi-face
    # note applies
    if disposition_override:
        result["disposition"] = disposition_override

    file_hash = audit.log_analysis(content, filename, result, model_version=MODEL_VERSION)
    result["file_sha256"] = file_hash

    return result

async def _run_analysis(filename: str, content: bytes, explain: bool) -> dict:
    """Async wrapper: offloads the blocking analysis pipeline to a worker
    thread so it doesn't stall the event loop for other in-flight requests."""
    return await asyncio.to_thread(_run_analysis_sync, filename, content, explain)

# Routes
@app.post("/api/v1/analyze", dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)])
async def analyze_media(file: UploadFile = File(...), explain: bool = Query(default=True)):
    logger.info(f"Analyzing asset: {file.filename}")
    content = await file.read()
    try:
        return await _run_analysis(file.filename, content, explain)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Batch files are processed concurrently, bounded by BATCH_CONCURRENCY so a
# large batch doesn't spawn 50 simultaneous model forward passes and blow
# out GPU/CPU memory. The actual model inference is further serialized
# inside model.py (see _inference_lock) — the concurrency win here comes
# from overlapping I/O-bound work (video decode, hashing, audit writes)
# across files while inference queues behind the lock.
BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "4"))

@app.post("/api/v1/analyze/batch", dependencies=[Depends(verify_api_key), Depends(enforce_rate_limit)])
async def analyze_batch(files: list[UploadFile] = File(...), explain: bool = Query(default=False)):
    """
    Analyze multiple files in one request. Each file is processed
    independently; a failure on one file does not abort the others —
    its entry in the response will contain an "error" field instead
    of the usual result fields.

    Explainability defaults to OFF for batch requests since GradCAM/attention
    maps are expensive and a batch is typically a screening pass, not a
    deep-dive on a single file.
    """

    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Batch size limited to 50 files per request.")

    logger.info(f"Batch analyzing {len(files)} assets")
    BATCH_SIZE.observe(len(files))

    semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def process_one(f: UploadFile) -> dict:
        content = await f.read()
        async with semaphore:
            try:
                return await _run_analysis(f.filename, content, explain)
            except HTTPException as e:
                return {"filename": f.filename, "error": e.detail}
            except Exception as e:
                logger.error(f"Batch item error ({f.filename}): {e}")
                return {"filename": f.filename, "error": str(e)}

    results = await asyncio.gather(*(process_one(f) for f in files))

    summary = {
        "total": len(results),
        "fake": sum(1 for r in results if r.get("verdict") == "FAKE"),
        "real": sum(1 for r in results if r.get("verdict") == "REAL"),
        "errors": sum(1 for r in results if "error" in r),
    }
    return {"summary": summary, "results": results}

@app.get("/api/v1/history", dependencies=[Depends(verify_api_key)])
async def history(limit: int = Query(default=50, le=200)):
    """Return recent audit log entries (chain-of-custody view)."""
    return {"entries": audit.get_recent(limit)}

@app.get("/api/v1/history/{file_hash}", dependencies=[Depends(verify_api_key)])
async def history_by_hash(file_hash: str):
    """Return all past analyses for a given SHA-256 file hash."""
    entries = audit.get_by_hash(file_hash)
    if not entries:
        raise HTTPException(status_code=404, detail="No records for this file hash.")
    return {"entries": entries}

@app.get("/health")
async def health():
    status = get_status()
    body = {"status": "ok" if status["model_loaded"] else "degraded", "version": MODEL_VERSION, **status}
    if not status["model_loaded"]:
        # A process that's up but never actually loaded the model (missing
        # weights, a load-time exception swallowed elsewhere) isn't really
        # healthy — it'll 500 on the first real request. Returning non-2xx
        # here is what makes the Docker/compose HEALTHCHECK meaningful
        # instead of just checking the port is open.
        raise HTTPException(status_code=503, detail=body)
    return body

@app.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint. Deliberately unauthenticated (like
    /health) to match standard scraper setups — restrict network access to
    it at the reverse-proxy/firewall level in any exposed deployment,
    same as you would for any other internal metrics endpoint."""
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)

# Static File Serving

# Point FastAPI to the folder where Vite is actually putting the files
_static = Path(__file__).parent / "static"

if _static.exists():
    # Mount the /assets folder so JS and CSS load correctly
    _assets = _static / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    # Serve the main HTML file at the root URL
    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(_static / "index.html"))
else:
    logger.warning(
        f"Frontend build directory not found at {_static}. "
        "Check your Vite configuration."
    )
