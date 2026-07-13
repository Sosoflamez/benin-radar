"""Lecture continue d'un flux caméra (RTSP ou fichier, Phase 4).
Contrairement à capture.iter_frames (lecture finie d'un fichier), ce module
ne suppose jamais que le flux se termine : il boucle jusqu'à should_stop()
ou jusqu'à un nombre de lectures échouées consécutives jugé irrécupérable."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import cv2

from apps.detection.pipeline.types import Frame

_MAX_CONSECUTIVE_READ_FAILURES = 10
_OPEN_TIMEOUT_MSEC = 10_000
_READ_TIMEOUT_MSEC = 10_000
_IDLE_POLL_S = 0.001


class StreamConnectionError(OSError):
    """Le flux n'a pas pu être ouvert."""


class StreamReadError(OSError):
    """Le flux s'est interrompu (lectures consécutives en échec)."""


def iter_stream_frames(
    stream_url: str,
    sample_fps: int,
    should_stop: Callable[[], bool],
    on_connected: Callable[[], None] | None = None,
) -> Iterator[Frame]:
    """Échantillonne un flux continu à sample_fps, cadencé sur l'horloge
    murale (pas de native_fps fiable sur un flux live). `on_connected`, si
    fourni, est appelé une fois la connexion établie, avant toute lecture —
    sert à corréler un repère horloge murale côté appelant (voir
    apps.detection.services.run_live_pipeline_for_camera) sans que ce module
    standalone dépende de Django."""
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise StreamConnectionError(f"Impossible d'ouvrir le flux : {stream_url}")
    # Best-effort : ignoré silencieusement si le backend ne le supporte pas.
    # Évite qu'une connexion RTSP gelée bloque capture.read() indéfiniment.
    capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, _OPEN_TIMEOUT_MSEC)
    capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, _READ_TIMEOUT_MSEC)
    try:
        if on_connected is not None:
            on_connected()
        started_at = time.monotonic()
        frame_interval_s = 1.0 / sample_fps
        next_due_at = started_at
        index = 0
        consecutive_failures = 0
        while not should_stop():
            read_ok, image = capture.read()
            if not read_ok:
                consecutive_failures += 1
                if consecutive_failures >= _MAX_CONSECUTIVE_READ_FAILURES:
                    raise StreamReadError(f"Flux interrompu : {stream_url}")
                continue
            consecutive_failures = 0
            now = time.monotonic()
            if now < next_due_at:
                time.sleep(_IDLE_POLL_S)
                continue
            yield Frame(index=index, timestamp_s=now - started_at, image=image)
            index += 1
            next_due_at += frame_interval_s
    finally:
        capture.release()
