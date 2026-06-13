# Model Card — ViT-CORE (vitcore_best.pth)

> ⚠️ **TODO**: The benchmark figures below are placeholders. The attached
> `ViT-CORE_Framework.pptx` contained only a title slide with no results data,
> so these numbers must be filled in from your actual training/evaluation logs
> before this card is published. Do not ship this card with placeholder
> numbers — an unfilled model card is worse than none, since it implies
> figures that were never measured.

## Overview

ViT-CORE is a Vision Transformer (`vit_small_patch16_224`) fine-tuned for
binary real/fake classification of face images, used as the core classifier
in the ViT-CORE-FORENSICS deepfake detection pipeline.

- **Architecture:** ViT-Small, patch size 16, input 224×224
- **Output:** 2-class softmax (index 0 = real, index 1 = fake)
- **Face extraction:** MTCNN (facenet-pytorch), margin=20px
- **Inference augmentation:** 4-view TTA (original, h-flip, center-crop+resize, h-flip of crop)

## Training Data

> TODO — fill in:
> - Dataset(s) used (e.g. FaceForensics++, CelebDF, DFDC, custom)
> - Compression levels used (c0/c23/c40 for FF++)
> - Train/val/test split sizes and methodology (split by identity, not by clip)
> - Class balance

## Benchmark Results

> TODO — fill in actual numbers from evaluate.py / metrics.py output.

| Test Set | Accuracy | AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| FaceForensics++ (c23) | TBD | TBD | TBD | TBD | TBD |
| CelebDF-v2 | TBD | TBD | TBD | TBD | TBD |
| DFDC | TBD | TBD | TBD | TBD | TBD |

## Known Limitations

- Face quality assessment thresholds (Laplacian variance, brightness) are
  calibrated heuristics, not learned from a dataset — they flag obviously
  poor inputs but are not a substitute for image-quality-aware training.
- The model has only been evaluated on the datasets listed above. Performance
  on manipulation methods or generators not represented in training data
  (e.g. newer diffusion-based face swaps) is unknown and likely degraded.
- Single-face detection only (`keep_all=False`) — videos with multiple faces
  are analyzed using only one face per frame, chosen by MTCNN's default
  selection (highest detection confidence).
- TTA and confidence-weighted frame aggregation reduce variance but do not
  eliminate it; `is_low_confidence` (0.4–0.6 probability range) should be
  treated as "no reliable verdict," not as a soft real/fake call.

## Intended Use

This system is designed as a **screening aid** for forensic analysts, not as
a standalone source of truth. Outputs should be corroborated with other
evidence before being used in any investigative or legal context. See
`explanation_summary.disclaimer` in API responses for the exact language
surfaced to end users.

## Versioning

| Version | Date | Notes |
|---|---|---|
| 2.0.0 | TBD | Current — attention rollout explainability, audit logging, batch endpoint |
| 1.0.0 | TBD | Initial FastAPI deployment |
