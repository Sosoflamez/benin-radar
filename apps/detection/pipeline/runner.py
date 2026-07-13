"""Orchestration standalone du pipeline vision : capture -> détection ->
tracking -> vitesse. Ne dépend pas de Django ; `config.model_weights_path`
doit déjà être un chemin résolu (résolution faite dans
apps/detection/services.py)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

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
    # Dernière frame vue par piste, écrasée à chaque frame : bornée par le
    # nombre de véhicules simultanément suivis, pas par la durée de la
    # vidéo. Sert de preuve/source de crop pour l'ANPR (apps/infractions,
    # apps/anpr) — approximation de l'instant de franchissement de sortie.
    latest_frame_by_track: dict[int, np.ndarray] = {}

    for frame in iter_frames(video_path, config.sample_fps):
        detections = [
            d for d in detector.detect(frame) if d.vehicle_class in config.vehicle_classes
        ]
        for tracked_detection in tracker.update(frame, detections):
            tracks[tracked_detection.track_id].append(tracked_detection)
            latest_frame_by_track[tracked_detection.track_id] = frame.image

    estimates = [
        replace(estimate, exit_frame=latest_frame_by_track.get(estimate.track_id))
        for track_detections in tracks.values()
        if (
            estimate := estimate_speed(
                track_detections, calibration, config.tracking_confidence_threshold
            )
        )
        is not None
    ]
    return sorted(estimates, key=lambda estimate: estimate.entered_at_s)
