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
    # Dernière frame vue du track (approximation du franchissement de sortie,
    # voir runner.py) — exclue de l'égalité/repr car une comparaison
    # d'ndarray n'est pas booléenne et le tableau est trop volumineux à afficher.
    exit_frame: np.ndarray | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class CalibrationData:
    """Miroir standalone de apps.cameras.models.CalibrationProfile."""

    homography_matrix: list[list[float]]
    reference_points: list[list[float]]
    measured_distance_m: float


# Délai d'abandon de piste par défaut de ByteTrack (apps/detection/pipeline/
# tracker.py), en appels à update() — donc en frames échantillonnées, pas en
# frames natives. Sert à valider track_timeout_s ci-dessous.
_BYTETRACK_LOST_TRACK_BUFFER_FRAMES = 30


@dataclass(frozen=True)
class PipelineConfig:
    sample_fps: int = 15
    detection_confidence_threshold: float = 0.4
    tracking_confidence_threshold: float = 0.5
    # Durée (secondes de flux) sans nouvelle détection avant de finaliser une
    # piste (mode streaming, Phase 4). Doit être strictement supérieure au
    # délai d'abandon interne de ByteTrack (_BYTETRACK_LOST_TRACK_BUFFER_FRAMES
    # / sample_fps) : sinon on finaliserait une piste avant que ByteTrack ne
    # l'abandonne lui-même, et une réapparition tardive sous le même track_id
    # produirait un second SpeedEstimate pour un seul passage réel.
    track_timeout_s: float = 3.0
    vehicle_classes: tuple[str, ...] = field(
        default_factory=lambda: ("car", "motorcycle", "bus", "truck")
    )
    model_weights_path: str | None = "yolov8n.pt"

    def __post_init__(self) -> None:
        min_timeout_s = _BYTETRACK_LOST_TRACK_BUFFER_FRAMES / self.sample_fps
        if self.track_timeout_s <= min_timeout_s:
            raise ValueError(
                f"track_timeout_s ({self.track_timeout_s}s) doit être strictement "
                f"supérieur au délai d'abandon de piste de ByteTrack "
                f"({min_timeout_s:.2f}s à {self.sample_fps} fps), sous peine de double "
                "comptage d'un même passage."
            )
