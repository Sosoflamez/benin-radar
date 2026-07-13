from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

from apps.cameras.factories import CalibrationProfileFactory, CameraFactory
from apps.detection.admin import VehicleDetectionAdmin
from apps.detection.factories import VehicleDetectionFactory
from apps.detection.models import VehicleDetection
from apps.detection.pipeline.stream import StreamConnectionError
from apps.detection.pipeline.types import SpeedEstimate
from apps.detection.services import (
    persist_speed_estimate,
    purge_detections_without_infraction,
    run_live_pipeline_for_camera,
    run_pipeline_for_camera,
)
from apps.detection.tasks import (
    _make_stop_checker,
    _run_with_reconnect,
    purge_stale_detections,
    run_camera_stream,
)
from apps.infractions.factories import InfractionFactory


@pytest.mark.django_db
class TestVehicleDetection:
    def test_str_contains_camera_and_speed(self):
        detection = VehicleDetectionFactory(
            camera__name="Porto-Novo Ouando", computed_speed_kmh="72.0"
        )
        text = str(detection)
        assert "Porto-Novo Ouando" in text
        assert "72.0" in text

    def test_most_recent_detection_first(self):
        first = VehicleDetectionFactory()
        second = VehicleDetectionFactory()
        assert list(VehicleDetection.objects.all()) == [second, first]


@pytest.mark.django_db
class TestVehicleDetectionAdmin:
    def test_detections_cannot_be_added_manually(self):
        admin = VehicleDetectionAdmin(VehicleDetection, AdminSite())
        request = RequestFactory().get("/")
        request.user = get_user_model().objects.create_superuser(
            username="root", email="root@benin-radar.bj", password="pw"
        )
        assert admin.has_add_permission(request) is False

    def test_all_fields_are_readonly(self):
        admin = VehicleDetectionAdmin(VehicleDetection, AdminSite())
        field_names = {f.name for f in VehicleDetection._meta.fields}
        assert set(admin.readonly_fields) == field_names


@pytest.mark.django_db
class TestPersistSpeedEstimate:
    def test_creates_vehicle_detection_from_estimate(self):
        camera = CameraFactory()
        estimate = SpeedEstimate(
            track_id=7,
            vehicle_class="motorcycle",
            entered_at_s=1.0,
            exited_at_s=2.5,
            speed_kmh=72.3,
            confidence=0.877,
            bbox_at_exit=[1.0, 2.0, 3.0, 4.0],
        )
        recorded_at = timezone.now()

        detection = persist_speed_estimate(camera, estimate, recorded_at)

        assert detection.camera == camera
        assert detection.track_id == 7
        assert detection.vehicle_class == "motorcycle"
        assert detection.zone_entered_at == recorded_at + timedelta(seconds=1.0)
        assert detection.zone_exited_at == recorded_at + timedelta(seconds=2.5)
        assert detection.computed_speed_kmh == Decimal("72.3")
        assert detection.tracking_confidence == Decimal("0.877")
        assert detection.bbox == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.django_db
class TestRunPipelineForCamera:
    def test_raises_without_calibration_profile(self, tmp_path):
        camera = CameraFactory()
        with pytest.raises(ValueError, match="calibration"):
            run_pipeline_for_camera(camera, tmp_path / "video.mp4")

    def test_persists_each_estimate(self, tmp_path, monkeypatch):
        camera = CameraFactory()
        CalibrationProfileFactory(camera=camera)
        estimate = SpeedEstimate(
            track_id=1,
            vehicle_class="car",
            entered_at_s=0.0,
            exited_at_s=1.0,
            speed_kmh=50.0,
            confidence=0.9,
            bbox_at_exit=[0.0, 0.0, 10.0, 10.0],
        )
        monkeypatch.setattr(
            "apps.detection.services.run_pipeline", lambda *args, **kwargs: [estimate]
        )

        detections = run_pipeline_for_camera(camera, tmp_path / "video.mp4")

        assert len(detections) == 1
        assert VehicleDetection.objects.count() == 1
        assert detections[0].camera == camera

    def test_evaluates_each_detection_for_infraction(self, tmp_path, monkeypatch):
        camera = CameraFactory()
        CalibrationProfileFactory(camera=camera)
        estimate = SpeedEstimate(
            track_id=1,
            vehicle_class="car",
            entered_at_s=0.0,
            exited_at_s=1.0,
            speed_kmh=50.0,
            confidence=0.9,
            bbox_at_exit=[0.0, 0.0, 10.0, 10.0],
        )
        monkeypatch.setattr(
            "apps.detection.services.run_pipeline", lambda *args, **kwargs: [estimate]
        )
        calls = []
        monkeypatch.setattr(
            "apps.detection.services.evaluate_detection_for_infraction",
            lambda detection, exit_frame: calls.append((detection, exit_frame)),
        )

        detections = run_pipeline_for_camera(camera, tmp_path / "video.mp4")

        assert len(calls) == 1
        assert calls[0][0] == detections[0]
        assert calls[0][1] is estimate.exit_frame


@pytest.mark.django_db
class TestRunLivePipelineForCamera:
    def test_raises_without_calibration_profile(self):
        camera = CameraFactory()
        with pytest.raises(ValueError, match="calibration"):
            run_live_pipeline_for_camera(camera, should_stop=lambda: True)

    def test_persists_and_evaluates_each_estimate(self, monkeypatch):
        camera = CameraFactory()
        CalibrationProfileFactory(camera=camera)
        estimate = SpeedEstimate(
            track_id=1,
            vehicle_class="car",
            entered_at_s=0.0,
            exited_at_s=1.0,
            speed_kmh=50.0,
            confidence=0.9,
            bbox_at_exit=[0.0, 0.0, 10.0, 10.0],
        )

        def fake_iter_stream_frames(stream_url, sample_fps, should_stop, on_connected=None):
            if on_connected is not None:
                on_connected()
            return iter([])

        monkeypatch.setattr("apps.detection.services.iter_stream_frames", fake_iter_stream_frames)
        monkeypatch.setattr(
            "apps.detection.services.run_streaming_pipeline",
            lambda frames, calibration, config: [estimate],
        )
        calls = []
        monkeypatch.setattr(
            "apps.detection.services.evaluate_detection_for_infraction",
            lambda detection, exit_frame: calls.append((detection, exit_frame)),
        )

        run_live_pipeline_for_camera(camera, should_stop=lambda: True)

        assert VehicleDetection.objects.count() == 1
        detection = VehicleDetection.objects.get()
        assert detection.camera == camera
        assert len(calls) == 1
        assert calls[0][0] == detection


@pytest.mark.django_db
class TestRunCameraStream:
    @pytest.fixture(autouse=True)
    def _locmem_cache(self, settings):
        # Verrou testé sans dépendre d'un vrai Redis (LocMemCache local à ce
        # processus de test suffit pour exercer cache.add/touch/delete).
        settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        cache.clear()

    def _lock_key(self, camera_id: int) -> str:
        return f"detection:camera-stream-lock:{camera_id}"

    def test_acquires_and_releases_lock_around_service_call(self, monkeypatch):
        camera = CameraFactory()
        calls = []
        monkeypatch.setattr(
            "apps.detection.tasks.run_live_pipeline_for_camera",
            lambda camera, should_stop: calls.append(camera),
        )

        result = run_camera_stream(camera.id)

        assert calls == [camera]
        assert result == f"Ingestion arrêtée pour « {camera.name} »."
        assert cache.get(self._lock_key(camera.id)) is None

    def test_returns_early_without_calling_service_when_lock_already_held(self, monkeypatch):
        camera = CameraFactory()
        cache.set(self._lock_key(camera.id), "other-task-id", timeout=60)
        calls = []
        monkeypatch.setattr(
            "apps.detection.tasks.run_live_pipeline_for_camera",
            lambda camera, should_stop: calls.append(camera),
        )

        result = run_camera_stream(camera.id)

        assert calls == []
        assert "déjà en cours" in result

    def test_returns_early_and_releases_lock_for_inactive_camera(self, monkeypatch):
        camera = CameraFactory(is_active=False)
        calls = []
        monkeypatch.setattr(
            "apps.detection.tasks.run_live_pipeline_for_camera",
            lambda camera, should_stop: calls.append(camera),
        )

        result = run_camera_stream(camera.id)

        assert calls == []
        assert "introuvable ou inactive" in result
        assert cache.get(self._lock_key(camera.id)) is None


@pytest.mark.django_db
class TestRunWithReconnect:
    def test_reconnects_after_stream_error_then_completes(self, monkeypatch):
        camera = CameraFactory()
        calls = []
        sleeps = []
        monkeypatch.setattr("apps.detection.tasks.time.sleep", lambda s: sleeps.append(s))

        def fake_run(camera_arg, should_stop):
            calls.append(camera_arg)
            if len(calls) == 1:
                raise StreamConnectionError("flux indisponible")

        monkeypatch.setattr("apps.detection.tasks.run_live_pipeline_for_camera", fake_run)

        _run_with_reconnect(camera, should_stop=lambda: False)

        assert calls == [camera, camera]
        assert sleeps == [5.0]

    def test_stops_without_retry_when_should_stop_becomes_true(self, monkeypatch):
        camera = CameraFactory()
        calls = []
        sleeps = []
        monkeypatch.setattr("apps.detection.tasks.time.sleep", lambda s: sleeps.append(s))

        def fake_run(camera_arg, should_stop):
            calls.append(camera_arg)
            raise StreamConnectionError("flux indisponible")

        monkeypatch.setattr("apps.detection.tasks.run_live_pipeline_for_camera", fake_run)

        state = {"checks": 0}

        def should_stop():
            state["checks"] += 1
            return state["checks"] > 1

        _run_with_reconnect(camera, should_stop=should_stop)

        assert calls == [camera]
        assert sleeps == []

    def test_never_calls_service_when_should_stop_true_from_the_start(self, monkeypatch):
        camera = CameraFactory()
        monkeypatch.setattr(
            "apps.detection.tasks.run_live_pipeline_for_camera",
            lambda camera, should_stop: pytest.fail("ne doit pas être appelé"),
        )

        _run_with_reconnect(camera, should_stop=lambda: True)


@pytest.mark.django_db
class TestMakeStopChecker:
    @pytest.fixture(autouse=True)
    def _locmem_cache(self, settings):
        settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        cache.clear()

    def _lock_key(self, camera_id: int) -> str:
        return f"detection:camera-stream-lock:{camera_id}"

    def test_returns_false_when_active_and_lock_held(self):
        camera = CameraFactory(is_active=True)
        lock_key = self._lock_key(camera.id)
        cache.set(lock_key, "task-id", timeout=60)

        assert _make_stop_checker(camera.id, lock_key)() is False

    def test_returns_true_when_camera_inactive(self):
        camera = CameraFactory(is_active=False)

        assert _make_stop_checker(camera.id, self._lock_key(camera.id))() is True

    def test_returns_true_when_lock_already_expired(self):
        camera = CameraFactory(is_active=True)
        # Verrou jamais posé/déjà expiré : cache.touch échoue, traité comme
        # un signal d'arrêt fatal (voir apps/detection/tasks.py).
        assert _make_stop_checker(camera.id, self._lock_key(camera.id))() is True

    def test_throttles_db_check_to_stop_check_interval(self):
        camera = CameraFactory(is_active=True)
        lock_key = self._lock_key(camera.id)
        cache.set(lock_key, "task-id", timeout=60)
        should_stop = _make_stop_checker(camera.id, lock_key)
        assert should_stop() is False

        camera.is_active = False
        camera.save()
        # Appel immédiat : throttlé, ne revérifie pas encore la base.
        assert should_stop() is False


@pytest.mark.django_db
class TestPurgeDetectionsWithoutInfraction:
    def _age(self, detection: VehicleDetection, days: int) -> None:
        VehicleDetection.objects.filter(pk=detection.pk).update(
            created_at=timezone.now() - timedelta(days=days)
        )

    def test_deletes_only_stale_detections_without_infraction(self):
        stale_without_infraction = VehicleDetectionFactory()
        self._age(stale_without_infraction, 10)

        stale_with_infraction = VehicleDetectionFactory()
        self._age(stale_with_infraction, 10)
        InfractionFactory(detection=stale_with_infraction)

        fresh_without_infraction = VehicleDetectionFactory()

        count = purge_detections_without_infraction(retention_days=7)

        assert count == 1
        remaining_ids = set(VehicleDetection.objects.values_list("id", flat=True))
        assert stale_without_infraction.id not in remaining_ids
        assert stale_with_infraction.id in remaining_ids
        assert fresh_without_infraction.id in remaining_ids

    def test_returns_zero_when_nothing_to_purge(self):
        VehicleDetectionFactory()
        assert purge_detections_without_infraction(retention_days=7) == 0


@pytest.mark.django_db
class TestPurgeStaleDetectionsTask:
    def test_delegates_to_service_with_configured_retention(self, settings):
        settings.DETECTION_RETENTION_DAYS = 7
        stale = VehicleDetectionFactory()
        VehicleDetection.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        assert purge_stale_detections() == 1
        assert not VehicleDetection.objects.filter(pk=stale.pk).exists()
