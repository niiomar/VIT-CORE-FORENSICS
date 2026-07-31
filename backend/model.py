import hashlib
import os
import threading
import torch
import numpy as np
import cv2
import base64
from torchvision import transforms
from torchvision.transforms import functional as F
from timm.models import vit_small_patch16_224
from PIL import Image
from facenet_pytorch import MTCNN

CHECKPOINT_PATH = os.getenv("MODEL_WEIGHTS_PATH", "vitcore_best.pth")
CHECKPOINT_SHA256 = os.getenv("MODEL_WEIGHTS_SHA256", "").strip().lower()
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_model = None
_mtcnn = None
_attention_cache = {}

# analyze_frame is invoked from worker threads (see main.py's use of
# asyncio.to_thread) so batches don't block the event loop. The QKV hook
# populates _attention_cache as a side effect of the forward pass, so the
# forward pass + heatmap read must be serialized to avoid one thread reading
# another thread's attention matrix.
_inference_lock = threading.Lock()

NORMALIZE = transforms.Normalize(mean=[0.5] * 3, std=[0.5] * 3)

# Quality ranking used for conservative aggregation across video frames.
# Higher = better.
QUALITY_RANK = {"Poor": 0, "N/A": 0, "Fair": 1, "High": 2}

def _verify_checkpoint_integrity(path: str) -> None:
    """Hash the checkpoint and log it, so an operator can capture it once
    from a known-good load and pin it via MODEL_WEIGHTS_SHA256. If that env
    var is set, refuse to start on a mismatch — this is a forensics tool,
    so a corrupted download or a silently swapped/tampered checkpoint should
    fail loudly, not produce quietly-wrong verdicts."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)
    digest = sha256.hexdigest()
    print(f"[ViT-CORE] Checkpoint SHA-256: {digest}")

    if CHECKPOINT_SHA256 and digest != CHECKPOINT_SHA256:
        raise RuntimeError(
            f"Checkpoint integrity check failed for {path}: expected "
            f"{CHECKPOINT_SHA256}, got {digest}. Refusing to load a "
            f"checkpoint that doesn't match MODEL_WEIGHTS_SHA256."
        )

def load_models():
    global _model, _mtcnn
    # keep_all=True detects every face in the frame instead of only the
    # largest — needed for analyze_all_faces below. MTCNN's default
    # select_largest=True still orders faces largest-first, so index 0 is
    # unchanged from the old keep_all=False behavior.
    _mtcnn = MTCNN(keep_all=True, device=DEVICE, post_process=False, image_size=224, margin=20)

    model = vit_small_patch16_224(pretrained=False, num_classes=2)
    if not os.path.exists(CHECKPOINT_PATH):
        print(f"[ViT-CORE] Warning: Checkpoint not found at {CHECKPOINT_PATH}. Using untrained weights.")
    else:
        _verify_checkpoint_integrity(CHECKPOINT_PATH)
        try:
            ckpt = torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True)
            sd = ckpt.get("model") or ckpt.get("model_state_dict") or ckpt
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning(
                "weights_only=True failed — falling back. Only safe with trusted checkpoints."
            )
            ckpt = torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=False)
            sd = ckpt.get("model") or ckpt.get("model_state_dict") or ckpt
        model.load_state_dict(sd)

    model.to(DEVICE)
    model.eval()
    if DEVICE.type == 'cuda':
        model.half()

    # Hook the QKV layer and manually compute the attention matrix
    def qkv_hook(module, input, output):
        try:
            B, N, C = output.shape
            num_heads = model.blocks[-1].attn.num_heads
            head_dim = (C // 3) // num_heads

            qkv = output.reshape(B, N, 3, num_heads, head_dim).permute(2, 0, 3, 1, 4)
            q, k, v = qkv.unbind(0)

            scale = head_dim ** -0.5
            attn = (q @ k.transpose(-2, -1)) * scale
            attn = attn.softmax(dim=-1)

            _attention_cache['last_attn'] = attn.detach().cpu().numpy()
        except Exception as e:
            print(f"[ViT-CORE] Heatmap generation error: {e}")

    try:
        model.blocks[-1].attn.qkv.register_forward_hook(qkv_hook)
    except Exception as e:
        print(f"[ViT-CORE] Could not hook QKV layer for heatmaps: {e}")

    _model = model
    print(f"[ViT-CORE] Models loaded on {DEVICE}")

def get_models():
    if _model is None or _mtcnn is None:
        load_models()
    return _model, _mtcnn

def get_status() -> dict:
    """Liveness/readiness details for /health — whether the model is
    actually usable, not just whether the process is up."""
    return {
        "model_loaded": _model is not None,
        "device": str(DEVICE),
        "weights_path": CHECKPOINT_PATH,
        "weights_found": os.path.exists(CHECKPOINT_PATH),
    }

def assess_face_quality(image: Image.Image) -> dict:
    cv_img = np.array(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)

    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = float(np.mean(gray))

    is_poor_lighting = brightness < 35 or brightness > 215

    if blur_score < 100.0 or is_poor_lighting:
        status = "Poor"
    elif blur_score < 350.0:
        status = "Fair"
    else:
        status = "High"

    return {"valid": status != "Poor", "status": status, "blur": round(blur_score, 1)}

def get_tta_views(image_tensor: torch.Tensor) -> torch.Tensor:
    view1 = image_tensor
    view2 = F.hflip(image_tensor)
    zoom = F.center_crop(image_tensor, output_size=(200, 200))
    zoom = F.resize(zoom, [224, 224])
    view3 = zoom
    view4 = F.hflip(zoom)

    views = torch.stack([view1, view2, view3, view4])
    views = torch.stack([NORMALIZE(v.float() / 255.0) for v in views])
    return views

def generate_explainability_visuals(image: Image.Image) -> dict:
    """Generates heatmap (JET), patch grid, and attention mask (INFERNO) in base64."""
    if 'last_attn' not in _attention_cache:
        return {"heatmap": "", "patches": "", "attention": ""}

    # 1. Base Image Prep
    cv_img = cv2.cvtColor(np.array(image.resize((224, 224))), cv2.COLOR_RGB2BGR)

    # 2. Generate PATCHES (Refined Tactical Grid)
    overlay = cv_img.copy()
    patch_size = 16
    for i in range(0, 224, patch_size):
        cv2.line(overlay, (i, 0), (i, 224), (0, 0, 0), 1)
        cv2.line(overlay, (0, i), (224, i), (0, 0, 0), 1)
        
    patch_img = cv2.addWeighted(overlay, 0.5, cv_img, 0.5, 0)
    _, buffer_patch = cv2.imencode('.jpg', patch_img)
    patches_b64 = base64.b64encode(buffer_patch).decode('utf-8')

    # 3. Process Neural Attention
    attn = _attention_cache['last_attn'][0]
    cls_attn = np.mean(attn[:, 0, 1:], axis=0) 
    
    grid_size = int(np.sqrt(len(cls_attn)))
    attention_grid = cls_attn.reshape((grid_size, grid_size))
    attention_grid = attention_grid / (np.max(attention_grid) + 1e-8)
    
    attention_grid = cv2.resize(attention_grid, (224, 224))
    attention_grid = cv2.GaussianBlur(attention_grid, (21, 21), 0)
    attention_grid = attention_grid / (np.max(attention_grid) + 1e-8)
    
    # 4. Generate ATTENTION (Inferno Colormap with Fallback)
    attention_inferno = np.uint8(255 * attention_grid)
    try:
        # Check if INFERNO exists, otherwise use JET
        if hasattr(cv2, 'COLORMAP_INFERNO'):
            attention_cmap = cv2.applyColorMap(attention_inferno, cv2.COLORMAP_INFERNO)
        else:
            attention_cmap = cv2.applyColorMap(attention_inferno, cv2.COLORMAP_JET)
    except Exception:
        # Final safety fallback
        attention_cmap = cv2.cvtColor(attention_inferno, cv2.COLOR_GRAY2BGR)

    # Blend the inferno map with a darkened version of the base image for spatial context
    dimmed_base = cv2.convertScaleAbs(cv_img, alpha=0.3, beta=0) # Drops brightness to 30%
    blended_attention = cv2.addWeighted(dimmed_base, 0.8, attention_cmap, 0.8, 0)

    _, buffer_attn = cv2.imencode('.jpg', blended_attention)
    attention_b64 = base64.b64encode(buffer_attn).decode('utf-8')

    # 5. Generate HEATMAP (Jet Colormap)
    heatmap_jet = np.uint8(255 * attention_grid)
    heatmap_jet = cv2.applyColorMap(heatmap_jet, cv2.COLORMAP_JET)
    superimposed = cv2.addWeighted(cv_img, 0.6, heatmap_jet, 0.4, 0)
    _, buffer_heat = cv2.imencode('.jpg', superimposed)
    heatmap_b64 = base64.b64encode(buffer_heat).decode('utf-8')

    return {
        "heatmap": heatmap_b64,
        "patches": patches_b64,
        "attention": attention_b64
    }

_EMPTY_VISUALS = {"heatmap": "", "patches": "", "attention": ""}

@torch.inference_mode()
def analyze_all_faces(image: Image.Image, generate_explainability: bool = False) -> list:
    """Detect and independently score every face in the image.

    Faces are returned largest-first (MTCNN's select_largest ordering), so
    index 0 is the "primary" subject a single-face caller should use. Each
    face gets its own MTCNN confidence gate, TTA batch, and ViT forward
    pass — scoring is fully independent per face, which is only safe to
    treat as ground truth within a single image. There's no identity
    tracking across video frames, so callers aggregating over a sequence of
    frames should not assume face N in frame A is the same person as face N
    in frame B (see analyze_frame, which sidesteps this entirely by only
    ever using the primary face).
    """
    model, mtcnn = get_models()

    try:
        boxes, probs = mtcnn.detect(image)
    except Exception as e:
        print(f"[ViT-CORE] MTCNN detection error: {e}")
        return []

    if boxes is None or probs is None or len(probs) == 0:
        return []

    # Reject artwork/pareidolia per-face: only score faces MTCNN is highly
    # confident about, rather than gating the whole image on the single
    # best detection.
    valid_indices = [i for i, p in enumerate(probs) if p is not None and p >= 0.98]
    if not valid_indices:
        print(f"[ViT-CORE] Face(s) rejected: low confidence (best={max(probs):.3f}). Likely OOD/Artwork.")
        return []

    face_tensors = mtcnn(image)  # (n, 3, 224, 224), same order as boxes/probs
    if face_tensors is None:
        return []

    results = []
    for i in valid_indices:
        if i >= face_tensors.shape[0]:
            continue
        face_tensor = face_tensors[i]

        display_img = F.to_pil_image(face_tensor / 255.0)
        face_quality = assess_face_quality(display_img)

        batch = get_tta_views(face_tensor).to(DEVICE)
        if DEVICE.type == 'cuda':
            batch = batch.half()

        # Serialized: the QKV hook writes to the shared _attention_cache, so
        # the forward pass and the heatmap read of that cache must be atomic
        # across concurrently-running worker threads (and across faces).
        with _inference_lock:
            out = model(batch)
            avg_logits = torch.mean(out, dim=0, keepdim=True)
            prob = torch.softmax(avg_logits, dim=1)[0, 1].item()
            visuals = generate_explainability_visuals(display_img) if generate_explainability else _EMPTY_VISUALS

        results.append({
            "probability": float(prob),
            "quality": face_quality,
            "visuals": visuals,
        })

    return results

def analyze_frame(image: Image.Image, generate_explainability=False):
    """Backward-compatible single-face view over analyze_all_faces: scores
    every face but returns only the primary (largest) one. This is what
    main.py's per-frame video aggregation uses, since it doesn't track face
    identity across frames — see analyze_all_faces directly for the full
    per-face breakdown (safe to use for a single image)."""
    faces = analyze_all_faces(image, generate_explainability)
    if not faces:
        return None, False, {"valid": False, "status": "N/A", "blur": 0}, _EMPTY_VISUALS

    primary = faces[0]
    return primary["probability"], True, primary["quality"], primary["visuals"]
