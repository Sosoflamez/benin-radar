from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from apps.cameras.factories import CalibrationProfileFactory, CameraFactory
from apps.detection.admin import VehicleDetectionAdmin
from apps.detection.factories import VehicleDetectionFactory
from apps.detection.models import VehicleDetection
from apps.detection.pipeline.types import SpeedEstimate
from apps.detection.services import persist_speed_estimate, run_pipeline_for_camera


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
