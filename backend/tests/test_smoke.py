"""
Smoke test: verifies the full inference pipeline runs end-to-end on CPU with
untrained weights (no vitcore_best.pth present in CI). This won't catch
accuracy regressions, but it catches import errors, shape mismatches, and
broken hooks before they hit main.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Force CPU and ensure no checkpoint is found (CI doesn't have weights)
os.environ["MODEL_WEIGHTS_PATH"] = "nonexistent.pth"

import model as vitcore_model  # noqa: E402


def test_pipeline_runs_on_blank_image():
    vitcore_model.load_models()

    blank = Image.fromarray(np.full((224, 224, 3), 128, dtype=np.uint8))
    prob, face_detected, quality, heatmap = vitcore_model.analyze_frame(
        blank, generate_explainability=True
    )

    assert 0.0 <= prob <= 1.0
    assert isinstance(face_detected, bool)
    assert quality["status"] in ("Poor", "Fair", "High", "N/A")
    # Heatmap should be a non-empty base64 string when explainability is on
    assert isinstance(heatmap, str)


def test_quality_assessment_thresholds():
    dark = Image.fromarray(np.full((224, 224, 3), 5, dtype=np.uint8))
    bright = Image.fromarray(np.full((224, 224, 3), 250, dtype=np.uint8))

    assert vitcore_model.assess_face_quality(dark)["status"] == "Poor"
    assert vitcore_model.assess_face_quality(bright)["status"] == "Poor"
