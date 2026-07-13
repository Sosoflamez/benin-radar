"""Orchestration standalone du pipeline vision : capture -> détection ->
tracking -> vitesse. Ne dépend pas de Django ; `config.model_weights_path`
doit déjà être un chemin résolu (résolution faite dans
apps/detection/services.py)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path

import numpy as np

from apps.detection.pipeline.capture import iter_frames
from apps.detection.pipeline.detector import VehicleDetector, YoloVehicleDetector
from apps.detection.pipeline.speed import estimate_speed
from apps.detection.pipeline.tracker import VehicleTracker
from apps.detection.pipeline.types import (
    CalibrationData,
    Frame,
    PipelineConfig,
    SpeedEstimate,
    TrackedDetection,
)


def _run_pipeline_frames(
    frames: Iterable[Frame],
    calibration: CalibrationData,
    config: PipelineConfig,
    detector: VehicleDetector | None,
) -> Iterator[SpeedEstimate]:
    """Cœur incrémental partagé par le mode fichier (run_pipeline) et le mode
    flux continu (run_streaming_pipeline) : consomme `frames` au fil de
    l'eau et finalise chaque piste (yield d'un SpeedEstimate) dès qu'elle
    devient inactive depuis `config.track_timeout_s`, plutôt que d'attendre
    la fin de l'itérable — indispensable pour un flux qui ne se termine
    jamais (RTSP), et sans effet sur le résultat pour un fichier fini tant
    qu'aucune piste n'a de trou interne ≥ track_timeout_s (elle est alors
    finalisée à la fin, comme avant ce refactor)."""
    if detector is None:
        detector = YoloVehicleDetector(
            config.model_weights_path, config.detection_confidence_threshold
        )
    tracker = VehicleTracker()
    tracks: dict[int, list[TrackedDetection]] = defaultdict(list)
    # Dernière frame vue par piste, écrasée à chaque frame : bornée par le
    # nombre de véhicules simultanément suivis, pas par la durée du flux.
    # Sert de preuve/source de crop pour l'ANPR (apps/infractions,
    # apps/anpr) — approximation de l'instant de franchissement de sortie.
    latest_frame_by_track: dict[int, np.ndarray] = {}
    last_seen_at: dict[int, float] = {}

    def _finalize(track_id: int) -> SpeedEstimate | None:
        track_detections = tracks.pop(track_id)
        frame_at_exit = latest_frame_by_track.pop(track_id, None)
        last_seen_at.pop(track_id, None)
        estimate = estimate_speed(
            track_detections, calibration, config.tracking_confidence_threshold
        )
        if estimate is None:
            return None
        return replace(estimate, exit_frame=frame_at_exit)

    for frame in frames:
        detections = [
            d for d in detector.detect(frame) if d.vehicle_class in config.vehicle_classes
        ]
        active_ids: set[int] = set()
        for tracked_detection in tracker.update(frame, detections):
            tracks[tracked_detection.track_id].append(tracked_detection)
            latest_frame_by_track[tracked_detection.track_id] = frame.image
            last_seen_at[tracked_detection.track_id] = frame.timestamp_s
            active_ids.add(tracked_detection.track_id)

        stale_ids = [
            track_id
            for track_id, seen_at in last_seen_at.items()
            if track_id not in active_ids and frame.timestamp_s - seen_at >= config.track_timeout_s
        ]
        for track_id in stale_ids:
            estimate = _finalize(track_id)
            if estimate is not None:
                yield estimate

    for track_id in list(tracks.keys()):
        estimate = _finalize(track_id)
        if estimate is not None:
            yield estimate


def run_pipeline(
    video_path: Path,
    calibration: CalibrationData,
    config: PipelineConfig,
    detector: VehicleDetector | None = None,
) -> list[SpeedEstimate]:
    """Traite un fichier vidéo de bout en bout et retourne les vitesses
    estimées, triées par heure d'entrée dans la zone."""
    frames = iter_frames(video_path, config.sample_fps)
    estimates = list(_run_pipeline_frames(frames, calibration, config, detector))
    return sorted(estimates, key=lambda estimate: estimate.entered_at_s)


def run_streaming_pipeline(
    frames: Iterable[Frame],
    calibration: CalibrationData,
    config: PipelineConfig,
    detector: VehicleDetector | None = None,
) -> Iterator[SpeedEstimate]:
    """Point d'entrée flux continu (Phase 4) : yield chaque SpeedEstimate dès
    que sa piste est finalisée, non trié — `frames` peut être infini (voir
    apps.detection.pipeline.stream.iter_stream_frames)."""
    yield from _run_pipeline_frames(frames, calibration, config, detector)
