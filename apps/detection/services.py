"""Persistance du pipeline vision dans les modèles Django (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.cameras.models import CalibrationProfile, Camera
from apps.detection.models import VehicleDetection
from apps.detection.pipeline.runner import run_pipeline
from apps.detection.pipeline.types import CalibrationData, PipelineConfig, SpeedEstimate
from apps.infractions.services import evaluate_detection_for_infraction


def calibration_data_from_profile(profile: CalibrationProfile) -> CalibrationData:
    """Convertit un CalibrationProfile Django en dataclass pipeline standalone."""
    return CalibrationData(
        homography_matrix=profile.homography_matrix,
        reference_points=profile.reference_points,
        measured_distance_m=float(profile.measured_distance_m),
    )


def pipeline_config_from_settings() -> PipelineConfig:
    """Construit la config pipeline à partir des réglages Django."""
    return PipelineConfig(
        sample_fps=settings.PIPELINE_SAMPLE_FPS,
        detection_confidence_threshold=settings.DETECTION_CONFIDENCE_THRESHOLD,
        tracking_confidence_threshold=settings.TRACKING_CONFIDENCE_THRESHOLD,
        model_weights_path=str(settings.ML_MODELS_DIR / settings.YOLO_MODEL_WEIGHTS),
    )


def persist_speed_estimate(
    camera: Camera, estimate: SpeedEstimate, recorded_at: datetime
) -> VehicleDetection:
    """Convertit une SpeedEstimate en VehicleDetection persistée."""
    return VehicleDetection.objects.create(
        camera=camera,
        track_id=estimate.track_id,
        vehicle_class=estimate.vehicle_class,
        zone_entered_at=recorded_at + timedelta(seconds=estimate.entered_at_s),
        zone_exited_at=recorded_at + timedelta(seconds=estimate.exited_at_s),
        computed_speed_kmh=Decimal(str(round(estimate.speed_kmh, 1))),
        tracking_confidence=Decimal(str(round(estimate.confidence, 3))),
        bbox=estimate.bbox_at_exit,
    )


def run_pipeline_for_camera(
    camera: Camera, video_path: Path, recorded_at: datetime | None = None
) -> list[VehicleDetection]:
    """Exécute le pipeline sur un fichier vidéo et persiste les détections
    résultantes. Lève ValueError si la caméra n'a pas de profil de
    calibration. `recorded_at` (par défaut l'heure courante) sert de départ
    pour convertir les timestamps relatifs du pipeline en horodatages
    absolus — approximation propre à l'offline, Phase 4 fournira de vrais
    timestamps par frame."""
    try:
        profile = camera.calibration_profile
    except CalibrationProfile.DoesNotExist:
        raise ValueError(f"La caméra « {camera.name} » n'a pas de profil de calibration.") from None

    calibration = calibration_data_from_profile(profile)
    config = pipeline_config_from_settings()
    estimates = run_pipeline(video_path, calibration, config)

    resolved_recorded_at = recorded_at or timezone.now()
    detections = []
    for estimate in estimates:
        detection = persist_speed_estimate(camera, estimate, resolved_recorded_at)
        evaluate_detection_for_infraction(detection, estimate.exit_frame)
        detections.append(detection)
    return detections
