from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
loaded = load_dotenv(dotenv_path=env_path)
print(f"[Config] .env loaded: {loaded} (path: {env_path})")
import logging
import time
import os
import cv2
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from model import analyze_frame, get_models
from auth import verify_api_key
import audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_VERSION = "2.0.0"
SUPPORTED_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.bmp')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing neural weights...")
    get_models()
    yield
    logger.info("Shutting down.")


app = FastAPI(title="ViT-CORE-FORENSICS API", version=MODEL_VERSION, lifespan=lifespan)

# Security: explicit origins and explicit headers — no wildcards.
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-KEY"],
)


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

async def extract_frames_to_pil(upload_file: UploadFile, content: bytes, num_frames=10):
    """Safely extracts frames using dynamic file suffix and converts to PIL Images."""
    file_suffix = Path(upload_file.filename).suffix.lower()
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


# ---------------------------------------------------------------------------
# Core analysis (shared by single + batch endpoints)
# ---------------------------------------------------------------------------

async def _run_analysis(file: UploadFile, content: bytes, explain: bool) -> dict:
    start_time = time.time()
    filename_lower = (file.filename or "").lower()

    if not filename_lower.endswith(SUPPORTED_EXTENSIONS):
        raise HTTPException(status_code=400, detail=f"Unsupported media format: {file.filename}")

    frames = await extract_frames_to_pil(file, content)
    if not frames:
        raise HTTPException(status_code=400, detail=f"Could not extract frames from {file.filename}.")

    frame_data = []
    heatmaps = []

    for frame in frames:
        prob, face_detected, face_quality, heatmap = analyze_frame(frame, generate_explainability=explain)
        frame_data.append({
            "probability": prob,
            "face_detected": face_detected,
            "quality": face_quality,
        })
        if heatmap:
            heatmaps.append(heatmap)

    probs = [f["probability"] for f in frame_data]
    weights = [abs(p - 0.5) for p in probs]
    weight_sum = sum(weights)

    agg_prob = (sum(p * w for p, w in zip(probs, weights)) / weight_sum
                if weight_sum > 0 else sum(probs) / len(probs))
    is_fake = agg_prob >= 0.5

    faces_found = any(f["face_detected"] for f in frame_data)

    # Conservative aggregation: report the WORST quality seen across all
    # frames where a face was detected, not just the first one. A single
    # blurry frame in an otherwise sharp video should still be flagged.
    quality_statuses = [f["quality"]["status"] for f in frame_data if f["face_detected"]]
    if quality_statuses:
        from model import QUALITY_RANK
        worst_status = min(quality_statuses, key=lambda s: QUALITY_RANK.get(s, 0))
        final_quality_status = worst_status
    else:
        final_quality_status = "N/A"

    result = {
        "verdict": "FAKE" if is_fake else "REAL",
        "confidence": round((agg_prob if is_fake else 1 - agg_prob) * 100, 1),
        "probability": round(float(agg_prob), 4),
        "processing_time_sec": round(time.time() - start_time, 2),
        "face_detected": faces_found,
        "face_quality": final_quality_status,
        "type": filename_lower.split('.')[-1],
        "frames_analyzed": len(probs),
        "is_low_confidence": (0.4 < agg_prob < 0.6),
        "explainability_maps": heatmaps,
        "filename": file.filename,
    }

    file_hash = audit.log_analysis(content, file.filename, result, model_version=MODEL_VERSION)
    result["file_sha256"] = file_hash

    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/v1/analyze", dependencies=[Depends(verify_api_key)])
async def analyze_media(file: UploadFile = File(...), explain: bool = Query(default=True)):
    logger.info(f"Analyzing asset: {file.filename}")
    content = await file.read()
    try:
        return await _run_analysis(file, content, explain)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/batch", dependencies=[Depends(verify_api_key)])
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
    results = []
    for f in files:
        content = await f.read()
        try:
            res = await _run_analysis(f, content, explain)
            results.append(res)
        except HTTPException as e:
            results.append({"filename": f.filename, "error": e.detail})
        except Exception as e:
            logger.error(f"Batch item error ({f.filename}): {e}")
            results.append({"filename": f.filename, "error": str(e)})

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
    return {"status": "ok", "version": MODEL_VERSION}


app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")
