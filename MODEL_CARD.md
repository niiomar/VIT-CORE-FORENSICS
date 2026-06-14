# Model Card — ViT-CORE (vitcore_best.pth)

## Overview

ViT-CORE is a Vision Transformer (ViT-S/16) deepfake detector that combines dual-view consistency learning with transformer-based global context modeling. The model is trained on FaceForensics++ (Low Quality / c40) and evaluated on both in-domain and cross-domain benchmarks.

- **Architecture:** ViT-Small (ViT-S/16), 12 transformer layers, 384-dimensional embeddings
- **Input Resolution:** 224 × 224
- **Output:** Binary classification (Real vs Fake)
- **Face Detection:** MTCNN with 1.3× bounding-box expansion
- **Consistency Learning:** Dual-view augmentation with Mean Squared Error (MSE) consistency loss
- **Pretraining:** ImageNet-1K pretrained weights
- **Training Epochs:** 30
- **Optimizer:** Adam (lr = 1e-4)

## Training Data

### Training Dataset
- **FaceForensics++ (Low Quality / c40)**
  - 1,000 real videos
  - 4,000 manipulated videos
  - Manipulation methods: Deepfakes, Face2Face, FaceSwap, NeuralTextures
  - Heavy compression setting (c40)

### Evaluation Datasets
- FaceForensics++ (LQ) Test Set
- Celeb-DF
- DFDC-Preview
- WildDeepfake

### Preprocessing
- Face extraction using MTCNN
- Bounding boxes enlarged by 1.3× to preserve facial context
- Faces resized to 224 × 224
- Image normalization using ImageNet statistics
- Weighted random sampling for class balancing

### Augmentation Strategy
Two independent views are generated for each image:

1. **RaAug**
   - No augmentation
   - Random erasing
   - Random resized crop

2. **DFDC_Selim**
   - JPEG compression
   - Gaussian noise
   - Gaussian blur
   - Random affine transformations
   - Random resized crop

## Benchmark Results

### In-Domain Evaluation

| Dataset | AUC (%) | Accuracy (%) |
|----------|----------|----------|
| FaceForensics++ (LQ) | 96.84 | 90.62 |

### Cross-Domain Evaluation

| Dataset | AUC (%) |
|----------|----------|
| Celeb-DF | 80.04 |
| DFDC-Preview | 76.37 |
| WildDeepfake | 75.01 |

### Comparison Against CORE Baseline

| Dataset | CORE AUC (%) | ViT-CORE AUC (%) |
|----------|----------|----------|
| FaceForensics++ (LQ) | 90.61 | 96.84 |
| Celeb-DF | 79.45 | 80.04 |
| DFDC-Preview | 75.74 | 76.37 |

## Training Configuration

- Batch Size: 32
- Learning Rate: 1 × 10⁻⁴
- Optimizer: Adam (β1=0.9, β2=0.999)
- Consistency Weight (Training): α = 5
- Consistency Weight (Cross-Domain Evaluation): α = 50–100
- Checkpoint Selection: Highest validation AUC

## Known Limitations

- Performance decreases under significant domain shift, from 96.84% AUC in-domain to approximately 75–80% AUC on unseen datasets.
- The framework operates on single frames and does not leverage temporal information available in videos.
- Performance on datasets and manipulation techniques outside the evaluation benchmark remains unknown.
- Strong real-world robustness against emerging diffusion-based face manipulation methods has not yet been established.
- The system analyzes facial content only and may be affected by face detection failures or extreme image degradation.

## Intended Use

This system is intended as a forensic screening and research tool for detecting manipulated facial imagery. Predictions should be treated as decision-support signals rather than definitive proof of authenticity or manipulation.

Human review and corroborating evidence are recommended before use in investigative, legal, journalistic, or security-sensitive contexts.

## Versioning

| Version | Date | Notes |
|----------|----------|----------|
| 2.0.0 | 2026 | ViT-S/16 backbone, MSE consistency regularization, cross-domain evaluation on Celeb-DF, DFDC-Preview, and WildDeepfake |
