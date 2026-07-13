"""Lecture échantillonnée d'un fichier vidéo."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import cv2

from apps.detection.pipeline.types import Frame


def iter_frames(video_path: Path, sample_fps: int) -> Iterator[Frame]:
    """Échantillonne une vidéo fichier à sample_fps, en sautant les frames
    natives excédentaires."""
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Impossible d'ouvrir la vidéo : {video_path}")
    try:
        native_fps = capture.get(cv2.CAP_PROP_FPS) or sample_fps
        frame_interval = max(1, round(native_fps / sample_fps))
        native_index = 0
        yielded = 0
        while True:
            read_ok, image = capture.read()
            if not read_ok:
                break
            if native_index % frame_interval == 0:
                yield Frame(index=yielded, timestamp_s=native_index / native_fps, image=image)
                yielded += 1
            native_index += 1
    finally:
        capture.release()
