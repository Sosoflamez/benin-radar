"""Estimation de vitesse par franchissement de deux lignes virtuelles.

Ligne A : y=0 (coordonnées monde). Ligne B : y=measured_distance_m. La
vitesse = distance réelle calibrée / Δt entre les deux franchissements,
moyennée sur plusieurs frames (lissage de la position monde), rejetée si la
confiance moyenne du suivi est sous le seuil.
"""

from __future__ import annotations

from collections import Counter

from apps.detection.pipeline.homography import image_point_to_world
from apps.detection.pipeline.types import CalibrationData, SpeedEstimate, TrackedDetection

_SMOOTHING_WINDOW = 3


def _moving_average(values: list[float], window: int = _SMOOTHING_WINDOW) -> list[float]:
    half = window // 2
    return [
        sum(values[max(0, i - half) : min(len(values), i + half + 1)])
        / len(values[max(0, i - half) : min(len(values), i + half + 1)])
        for i in range(len(values))
    ]


def _find_crossing_time(times: list[float], values: list[float], target: float) -> float | None:
    for i in range(1, len(values)):
        previous, current = values[i - 1], values[i]
        if previous == target:
            return times[i - 1]
        if (previous - target) * (current - target) < 0:
            fraction = (target - previous) / (current - previous)
            return times[i - 1] + fraction * (times[i] - times[i - 1])
    if values and values[-1] == target:
        return times[-1]
    return None


def estimate_speed(
    track_detections: list[TrackedDetection],
    calibration: CalibrationData,
    tracking_confidence_threshold: float,
) -> SpeedEstimate | None:
    """Calcule la vitesse d'un track. Retourne None si la confiance moyenne
    est sous le seuil ou si les deux lignes virtuelles ne sont pas
    franchies."""
    if not track_detections:
        return None

    samples = sorted(track_detections, key=lambda d: d.timestamp_s)
    mean_confidence = sum(d.confidence for d in samples) / len(samples)
    if mean_confidence < tracking_confidence_threshold:
        return None

    world_points = [
        image_point_to_world(
            ((detection.bbox[0] + detection.bbox[2]) / 2, detection.bbox[3]),
            calibration.homography_matrix,
        )
        for detection in samples
    ]
    smoothed_y = _moving_average([point[1] for point in world_points])
    times = [detection.timestamp_s for detection in samples]

    entered_at_s = _find_crossing_time(times, smoothed_y, 0.0)
    exited_at_s = _find_crossing_time(times, smoothed_y, calibration.measured_distance_m)
    if entered_at_s is None or exited_at_s is None or entered_at_s == exited_at_s:
        return None

    duration_s = abs(exited_at_s - entered_at_s)
    speed_kmh = calibration.measured_distance_m / duration_s * 3.6
    vehicle_class = Counter(d.vehicle_class for d in samples).most_common(1)[0][0]
    exit_sample = min(samples, key=lambda d: abs(d.timestamp_s - exited_at_s))

    return SpeedEstimate(
        track_id=samples[0].track_id,
        vehicle_class=vehicle_class,
        entered_at_s=entered_at_s,
        exited_at_s=exited_at_s,
        speed_kmh=speed_kmh,
        confidence=mean_confidence,
        bbox_at_exit=exit_sample.bbox,
    )
