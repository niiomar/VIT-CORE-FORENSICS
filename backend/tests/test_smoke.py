"""
Smoke test: verifies the full inference pipeline runs end-to-end on CPU with
untrained weights (no vitcore_best.pth present in CI). This won't catch
accuracy regressions, but it catches import errors, shape mismatches, and
broken hooks before they hit main.
"""

import os
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# Force CPU and ensure no checkpoint is found (CI doesn't have weights)
os.environ["MODEL_WEIGHTS_PATH"] = "nonexistent.pth"

import model as vitcore_model  # noqa: E402


def test_pipeline_handles_no_face_detected():
    """A blank/uniform image has no detectable face, so MTCNN should bypass
    the ViT entirely — this is the normal "no subject" response shape, not
    an error."""
    vitcore_model.load_models()

    blank = Image.fromarray(np.full((224, 224, 3), 128, dtype=np.uint8))
    prob, face_detected, quality, visuals = vitcore_model.analyze_frame(
        blank, generate_explainability=True
    )

    assert prob is None
    assert face_detected is False
    assert quality["status"] == "N/A"
    assert visuals == {"heatmap": "", "patches": "", "attention": ""}


def test_pipeline_runs_full_path(monkeypatch):
    """Exercises the ViT forward pass, TTA, and attention-rollout heatmap
    generation directly by mocking MTCNN's detection/extraction, since CI
    has no real face-containing fixture image. This is what actually
    catches import errors, shape mismatches, and broken hooks — the class
    of regression this smoke test exists for."""
    vitcore_model.load_models()

    # MTCNN(keep_all=True) always returns a stacked (n, 3, H, W) tensor,
    # even for a single face — see facenet_pytorch's MTCNN.extract().
    fake_face_tensors = torch.full((1, 3, 224, 224), 128.0)
    monkeypatch.setattr(
        vitcore_model._mtcnn, "detect",
        lambda img: (np.array([[0, 0, 224, 224]]), np.array([0.999])),
    )
    monkeypatch.setattr(
        type(vitcore_model._mtcnn), "__call__", lambda self, img: fake_face_tensors
    )

    blank = Image.fromarray(np.full((224, 224, 3), 128, dtype=np.uint8))
    prob, face_detected, quality, visuals = vitcore_model.analyze_frame(
        blank, generate_explainability=True
    )

    assert 0.0 <= prob <= 1.0
    assert face_detected is True
    assert quality["status"] in ("Poor", "Fair", "High")

    # Heatmap should be a non-empty base64 string when explainability is on
    assert isinstance(visuals, dict)
    assert isinstance(visuals["heatmap"], str) and visuals["heatmap"] != ""


def test_analyze_all_faces_multi_face(monkeypatch):
    """Multiple faces in one image should each get an independent verdict,
    and analyze_frame's backward-compat wrapper should still surface only
    the primary (first/largest) one."""
    vitcore_model.load_models()

    fake_face_tensors = torch.full((2, 3, 224, 224), 128.0)
    monkeypatch.setattr(
        vitcore_model._mtcnn, "detect",
        lambda img: (
            np.array([[0, 0, 100, 100], [120, 120, 224, 224]]),
            np.array([0.999, 0.995]),
        ),
    )
    monkeypatch.setattr(
        type(vitcore_model._mtcnn), "__call__", lambda self, img: fake_face_tensors
    )

    blank = Image.fromarray(np.full((224, 224, 3), 128, dtype=np.uint8))

    faces = vitcore_model.analyze_all_faces(blank, generate_explainability=False)
    assert len(faces) == 2
    for f in faces:
        assert 0.0 <= f["probability"] <= 1.0
        assert f["quality"]["status"] in ("Poor", "Fair", "High")

    prob, face_detected, quality, visuals = vitcore_model.analyze_frame(blank)
    assert face_detected is True
    assert prob == faces[0]["probability"]


def test_analyze_all_faces_rejects_low_confidence_detections(monkeypatch):
    """A face below the 0.98 OOD gate should be dropped, not crash or get
    silently scored alongside genuine detections."""
    vitcore_model.load_models()

    fake_face_tensors = torch.full((2, 3, 224, 224), 128.0)
    monkeypatch.setattr(
        vitcore_model._mtcnn, "detect",
        lambda img: (
            np.array([[0, 0, 100, 100], [120, 120, 224, 224]]),
            np.array([0.999, 0.5]),  # second detection is below the gate
        ),
    )
    monkeypatch.setattr(
        type(vitcore_model._mtcnn), "__call__", lambda self, img: fake_face_tensors
    )

    blank = Image.fromarray(np.full((224, 224, 3), 128, dtype=np.uint8))
    faces = vitcore_model.analyze_all_faces(blank, generate_explainability=False)
    assert len(faces) == 1


def test_quality_assessment_thresholds():
    dark = Image.fromarray(np.full((224, 224, 3), 5, dtype=np.uint8))
    bright = Image.fromarray(np.full((224, 224, 3), 250, dtype=np.uint8))

    assert vitcore_model.assess_face_quality(dark)["status"] == "Poor"
    assert vitcore_model.assess_face_quality(bright)["status"] == "Poor"
