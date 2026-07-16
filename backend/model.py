import os
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
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_model = None
_mtcnn = None
_attention_cache = {}

NORMALIZE = transforms.Normalize(mean=[0.5] * 3, std=[0.5] * 3)

# Quality ranking used for conservative aggregation across video frames.
# Higher = better.
QUALITY_RANK = {"Poor": 0, "N/A": 0, "Fair": 1, "High": 2}


def load_models():
    global _model, _mtcnn
    _mtcnn = MTCNN(keep_all=False, device=DEVICE, post_process=False, image_size=224, margin=20)

    model = vit_small_patch16_224(pretrained=False, num_classes=2)
    if not os.path.exists(CHECKPOINT_PATH):
        print(f"[ViT-CORE] Warning: Checkpoint not found at {CHECKPOINT_PATH}. Using untrained weights.")
    else:
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
    
    # 4. Generate ATTENTION (Inferno Colormap)
    attention_inferno = np.uint8(255 * attention_grid)
    attention_inferno = cv2.applyColorMap(attention_inferno, cv2.COLORMAP_INFERNO)
    _, buffer_attn = cv2.imencode('.jpg', attention_inferno)
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


@torch.inference_mode()
def analyze_frame(image: Image.Image, generate_explainability=False):
    model, mtcnn = get_models()

    face_tensor = mtcnn(image)
    face_detected = True
    face_quality = {"valid": False, "status": "N/A", "blur": 0}

    if face_tensor is None:
        face_detected = False
        face_tensor = transforms.ToTensor()(image.resize((224, 224))) * 255.0
        display_img = image
    else:
        display_img = F.to_pil_image(face_tensor / 255.0)
        face_quality = assess_face_quality(display_img)

    batch = get_tta_views(face_tensor).to(DEVICE)
    if DEVICE.type == 'cuda':
        batch = batch.half()

    out = model(batch)
    avg_logits = torch.mean(out, dim=0, keepdim=True)
    prob = torch.softmax(avg_logits, dim=1)[0, 1].item()

    visuals = generate_explainability_visuals(display_img) if generate_explainability else {"heatmap": "", "patches": "", "attention": ""}

    return float(prob), face_detected, face_quality, visuals
