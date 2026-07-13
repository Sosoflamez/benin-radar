"""Orchestration standalone du pipeline vision : capture -> détection ->
tracking -> vitesse. Ne dépend pas de Django ; `config.model_weights_path`
doit déjà être un chemin résolu (résolution faite dans
apps/detection/services.py)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from apps.detection.pipeline.capture import iter_frames
from apps.detection.pipeline.detector import VehicleDetector, YoloVehicleDetector
from apps.detection.pipeline.speed import estimate_speed
from apps.detection.pipeline.tracker import VehicleTracker
from apps.detection.pipeline.types import (
    CalibrationData,
    PipelineConfig,
    SpeedEstimate,
    TrackedDetection,
)


def run_pipeline(
    video_path: Path,
    calibration: CalibrationData,
    config: PipelineConfig,
    detector: VehicleDetector | None = None,
) -> list[SpeedEstimate]:
    """Traite un fichier vidéo de bout en bout et retourne les vitesses
    estimées, triées par heure d'entrée dans la zone."""
    if detector is None:
        detector = YoloVehicleDetector(
            config.model_weights_path, config.detection_confidence_threshold
        )
    tracker = VehicleTracker()
    tracks: dict[int, list[TrackedDetection]] = defaultdict(list)

    for frame in iter_frames(video_path, config.sample_fps):
        detections = [
            d for d in detector.detect(frame) if d.vehicle_class in config.vehicle_classes
        ]
        for tracked_detection in tracker.update(frame, detections):
            tracks[tracked_detection.track_id].append(tracked_detection)

    estimates = [
        estimate
        for track_detections in tracks.values()
        if (
            estimate := estimate_speed(
                track_detections, calibration, config.tracking_confidence_threshold
            )
        )
        is not None
    ]
    return sorted(estimates, key=lambda estimate: estimate.entered_at_s)
