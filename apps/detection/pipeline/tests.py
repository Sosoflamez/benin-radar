"""Tests du pipeline vision standalone (aucun accès base de données)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from apps.detection.pipeline.capture import iter_frames
from apps.detection.pipeline.homography import compute_homography, image_point_to_world
from apps.detection.pipeline.runner import run_pipeline
from apps.detection.pipeline.speed import estimate_speed
from apps.detection.pipeline.tracker import VehicleTracker
from apps.detection.pipeline.types import (
    CalibrationData,
    Detection,
    Frame,
    PipelineConfig,
    TrackedDetection,
)

IDENTITY_MATRIX = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


class TestComputeHomography:
    def test_identical_rectangles_give_identity(self):
        matrix = compute_homography(
            reference_points=[[0, 0], [10, 0], [10, 10], [0, 10]],
            lane_width_m=10,
            measured_distance_m=10,
        )
        world_point = image_point_to_world((5, 5), matrix)
        assert world_point == pytest.approx((5.0, 5.0), abs=1e-4)


class TestImagePointToWorld:
    def test_identity_matrix_is_a_no_op(self):
        assert image_point_to_world((3.0, 4.0), IDENTITY_MATRIX) == pytest.approx((3.0, 4.0))


class TestEstimateSpeed:
    def _calibration(self, measured_distance_m: float = 20.0) -> CalibrationData:
        return CalibrationData(
            homography_matrix=IDENTITY_MATRIX,
            reference_points=[
                [0, 0],
                [3.5, 0],
                [3.5, measured_distance_m],
                [0, measured_distance_m],
            ],
            measured_distance_m=measured_distance_m,
        )

    def _track(self, confidence: float) -> list[TrackedDetection]:
        # y ramps linéairement de -10 à 30 (padding avant/après les deux
        # lignes virtuelles y=0 et y=20) pour un lissage à marge confortable.
        values = [-10, -5, 0, 5, 10, 15, 20, 25, 30]
        times = [i * 0.5 - 1.0 for i in range(len(values))]
        return [
            TrackedDetection(
                track_id=1,
                frame_index=i,
                timestamp_s=t,
                bbox=[0.0, y - 5.0, 0.0, y],
                vehicle_class="car",
                confidence=confidence,
            )
            for i, (t, y) in enumerate(zip(times, values, strict=True))
        ]

    def test_computes_plausible_speed(self):
        estimate = estimate_speed(
            self._track(confidence=0.9), self._calibration(), tracking_confidence_threshold=0.5
        )
        assert estimate is not None
        assert estimate.entered_at_s == pytest.approx(0.0, abs=1e-6)
        assert estimate.exited_at_s == pytest.approx(2.0, abs=1e-6)
        assert estimate.speed_kmh == pytest.approx(36.0, abs=1e-3)
        assert estimate.vehicle_class == "car"

    def test_rejects_low_confidence_track(self):
        estimate = estimate_speed(
            self._track(confidence=0.3), self._calibration(), tracking_confidence_threshold=0.5
        )
        assert estimate is None

    def test_rejects_track_without_crossing(self):
        track = self._track(confidence=0.9)[:2]  # ne franchit aucune des deux lignes
        estimate = estimate_speed(track, self._calibration(), tracking_confidence_threshold=0.5)
        assert estimate is None


class TestIterFrames:
    def test_samples_down_to_target_fps(self, synthetic_video: Path):
        frames = list(iter_frames(synthetic_video, sample_fps=10))
        assert len(frames) == 10
        assert frames[0].image.shape == (480, 640, 3)

    def test_raises_for_missing_file(self, tmp_path: Path):
        with pytest.raises(OSError):
            list(iter_frames(tmp_path / "missing.mp4", sample_fps=10))


class TestVehicleTracker:
    def test_assigns_stable_track_id_across_frames(self):
        tracker = VehicleTracker()
        image = np.zeros((10, 10, 3), dtype=np.uint8)

        first = tracker.update(
            Frame(index=0, timestamp_s=0.0, image=image),
            [Detection(bbox=[10, 10, 50, 50], vehicle_class="car", confidence=0.9)],
        )
        second = tracker.update(
            Frame(index=1, timestamp_s=0.1, image=image),
            [Detection(bbox=[12, 10, 52, 50], vehicle_class="car", confidence=0.9)],
        )

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].track_id == second[0].track_id


class TestRunPipeline:
    def test_end_to_end_with_fake_detector(self, synthetic_video: Path, fake_detector_factory):
        # y ramp de -20 à 36 sur 15 frames (indices échantillonnés par
        # iter_frames à sample_fps=15 sur une vidéo native à 30 fps).
        detections_by_frame = {
            i: [
                Detection(
                    bbox=[10.0, -20 + i * 4 - 10, 50.0, -20 + i * 4],
                    vehicle_class="car",
                    confidence=0.9,
                )
            ]
            for i in range(15)
        }
        detector = fake_detector_factory(detections_by_frame)
        calibration = CalibrationData(
            homography_matrix=IDENTITY_MATRIX,
            reference_points=[[0, 0], [3.5, 0], [3.5, 20], [0, 20]],
            measured_distance_m=20.0,
        )
        config = PipelineConfig(sample_fps=15, tracking_confidence_threshold=0.5)

        estimates = run_pipeline(synthetic_video, calibration, config, detector=detector)

        assert len(estimates) == 1
        assert estimates[0].vehicle_class == "car"
        assert estimates[0].speed_kmh > 0
        assert estimates[0].exit_frame is not None
        assert estimates[0].exit_frame.shape == (480, 640, 3)
