"""Dataclasses du pipeline vision. Aucune dépendance Django : ce module doit
rester utilisable de façon autonome (voir apps/detection/services.py pour la
persistance)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Frame:
    index: int
    timestamp_s: float
    image: np.ndarray


@dataclass(frozen=True)
class Detection:
    bbox: list[float]  # [x1, y1, x2, y2]
    vehicle_class: str
    confidence: float


@dataclass(frozen=True)
class TrackedDetection:
    track_id: int
    frame_index: int
    timestamp_s: float
    bbox: list[float]
    vehicle_class: str
    confidence: float


@dataclass(frozen=True)
class SpeedEstimate:
    track_id: int
    vehicle_class: str
    entered_at_s: float
    exited_at_s: float
    speed_kmh: float
    confidence: float
    bbox_at_exit: list[float]


@dataclass(frozen=True)
class CalibrationData:
    """Miroir standalone de apps.cameras.models.CalibrationProfile."""

    homography_matrix: list[list[float]]
    reference_points: list[list[float]]
    measured_distance_m: float


@dataclass(frozen=True)
class PipelineConfig:
    sample_fps: int = 15
    detection_confidence_threshold: float = 0.4
    tracking_confidence_threshold: float = 0.5
    vehicle_classes: tuple[str, ...] = field(
        default_factory=lambda: ("car", "motorcycle", "bus", "truck")
    )
    model_weights_path: str | None = "yolov8n.pt"
