"""Fixtures partagées pour les tests de apps.detection (Django et pipeline
standalone)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from apps.detection.pipeline.types import Detection, Frame


class FakeVehicleDetector:
    """Détecteur de test : détections prédéfinies par index de frame, aucun
    poids de modèle requis."""

    def __init__(self, detections_by_frame: dict[int, list[Detection]]) -> None:
        self._detections_by_frame = detections_by_frame

    def detect(self, frame: Frame) -> list[Detection]:
        return self._detections_by_frame.get(frame.index, [])


@pytest.fixture
def fake_detector_factory():
    """Fabrique un FakeVehicleDetector à partir d'un mapping
    frame_index -> détections."""

    def _factory(detections_by_frame: dict[int, list[Detection]]) -> FakeVehicleDetector:
        return FakeVehicleDetector(detections_by_frame)

    return _factory


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    """Génère une courte vidéo mp4 synthétique (rectangle en mouvement) dans
    tmp_path, jamais dans tests/fixtures/videos/ (réservé à un futur fixture
    téléchargé, pas committé)."""
    video_path = tmp_path / "synthetic.mp4"
    width, height, fps, num_frames = 640, 480, 30, 30
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for i in range(num_frames):
        image = np.zeros((height, width, 3), dtype=np.uint8)
        x = int(i * (width - 100) / num_frames)
        cv2.rectangle(image, (x, 200), (x + 80, 260), (255, 255, 255), -1)
        writer.write(image)
    writer.release()
    return video_path
