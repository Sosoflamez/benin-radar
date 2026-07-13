"""Suivi inter-frames des véhicules détectés via ByteTrack (supervision)."""

from __future__ import annotations

import numpy as np
import supervision as sv

from apps.detection.pipeline.types import Detection, Frame, TrackedDetection

_CLASS_TO_ID: dict[str, int] = {"car": 0, "motorcycle": 1, "bus": 2, "truck": 3}
_ID_TO_CLASS: dict[int, str] = {value: key for key, value in _CLASS_TO_ID.items()}


class VehicleTracker:
    """Encapsule ByteTrack pour attribuer un track_id stable aux détections
    au fil des frames."""

    def __init__(self) -> None:
        self._byte_track = sv.ByteTrack()

    def update(self, frame: Frame, detections: list[Detection]) -> list[TrackedDetection]:
        sv_detections = sv.Detections(
            xyxy=np.array([d.bbox for d in detections], dtype=np.float32).reshape(-1, 4),
            confidence=np.array([d.confidence for d in detections], dtype=np.float32),
            class_id=np.array([_CLASS_TO_ID[d.vehicle_class] for d in detections], dtype=int),
        )
        tracked = self._byte_track.update_with_detections(sv_detections)
        return [
            TrackedDetection(
                track_id=int(tracked.tracker_id[i]),
                frame_index=frame.index,
                timestamp_s=frame.timestamp_s,
                bbox=[float(v) for v in tracked.xyxy[i]],
                vehicle_class=_ID_TO_CLASS[int(tracked.class_id[i])],
                confidence=float(tracked.confidence[i]),
            )
            for i in range(len(tracked))
        ]
