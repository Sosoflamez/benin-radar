"""Détection de véhicules par frame. `VehicleDetector` est un Protocol pour
permettre l'injection d'un faux détecteur en test, sans télécharger de poids
réels."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ultralytics import YOLO

from apps.detection.pipeline.types import Detection, Frame


class VehicleDetector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]: ...


class YoloVehicleDetector:
    """Détecteur YOLOv8, filtré aux classes véhicules pertinentes pour le
    Bénin (motos/zémidjans incluses)."""

    _COCO_CLASS_MAP: dict[int, str] = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    def __init__(self, weights_path: str | Path, confidence_threshold: float = 0.4) -> None:
        self._model = YOLO(str(weights_path))
        self._confidence_threshold = confidence_threshold

    def detect(self, frame: Frame) -> list[Detection]:
        results = self._model.predict(frame.image, conf=self._confidence_threshold, verbose=False)
        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                vehicle_class = self._COCO_CLASS_MAP.get(int(box.cls[0]))
                if vehicle_class is None:
                    continue
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0])
                detections.append(
                    Detection(
                        bbox=[x1, y1, x2, y2],
                        vehicle_class=vehicle_class,
                        confidence=float(box.conf[0]),
                    )
                )
        return detections
