import hashlib
import io
from decimal import Decimal

import numpy as np
import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from PIL import Image

from apps.cameras.factories import CameraFactory
from apps.detection.factories import VehicleDetectionFactory
from apps.infractions.admin import EvidenceAdmin, InfractionAdmin
from apps.infractions.factories import InfractionFactory
from apps.infractions.models import Evidence, Infraction
from apps.infractions.services import create_evidence, evaluate_detection_for_infraction


def _fake_image_file(name="proof.jpg") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
class TestCreateEvidence:
    def test_computes_sha256_of_full_image(self):
        infraction = InfractionFactory()
        image_file = _fake_image_file()
        expected_hash = hashlib.sha256(image_file.read()).hexdigest()
        image_file.seek(0)

        evidence = create_evidence(infraction, image_file)

        assert evidence.sha256_hash == expected_hash
        assert evidence.infraction == infraction

    def test_defaults_metadata_to_empty_dict(self):
        infraction = InfractionFactory()
        evidence = create_evidence(infraction, _fake_image_file())
        assert evidence.metadata == {}


@pytest.mark.django_db
class TestInfraction:
    def test_str_contains_camera_speed_and_status(self):
        infraction = InfractionFactory(recorded_speed_kmh="90.0", camera__name="Abomey-Calavi")
        text = str(infraction)
        assert "Abomey-Calavi" in text
        assert "90.0" in text
        assert "detectee" in text

    def test_is_never_deletable_from_admin(self):
        admin = InfractionAdmin(Infraction, AdminSite())
        superuser = get_user_model().objects.create_superuser(
            username="root", email="root@benin-radar.bj", password="pw"
        )
        request = RequestFactory().get("/")
        request.user = superuser
        assert admin.has_delete_permission(request) is False


@pytest.mark.django_db
class TestEvidenceAdmin:
    def test_is_never_deletable_from_admin(self):
        admin = EvidenceAdmin(Evidence, AdminSite())
        superuser = get_user_model().objects.create_superuser(
            username="root2", email="root2@benin-radar.bj", password="pw"
        )
        request = RequestFactory().get("/")
        request.user = superuser
        assert admin.has_delete_permission(request) is False


@pytest.mark.django_db
class TestAgentsGroup:
    def test_created_by_migration_with_expected_permissions(self):
        group = Group.objects.get(name="Agents")
        codenames = set(group.permissions.values_list("codename", flat=True))
        assert codenames == {
            "view_plate_data",
            "view_evidence",
            "view_infraction",
            "change_infraction",
        }


class _FakeTask:
    """Remplace apps.anpr.tasks.read_plate_for_evidence.delay pendant les
    tests, sans nécessiter de broker Celery."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def delay(self, evidence_id: int) -> None:
        self.calls.append(evidence_id)


@pytest.mark.django_db
class TestEvaluateDetectionForInfraction:
    def _exit_frame(self) -> np.ndarray:
        return np.zeros((5, 5, 3), dtype=np.uint8)

    def test_creates_infraction_and_evidence_when_speeding(self, monkeypatch):
        fake_task = _FakeTask()
        monkeypatch.setattr("apps.anpr.tasks.read_plate_for_evidence", fake_task)
        camera = CameraFactory(speed_limit_kmh=60)
        detection = VehicleDetectionFactory(camera=camera, computed_speed_kmh="90.0")

        infraction = evaluate_detection_for_infraction(detection, self._exit_frame())

        assert infraction is not None
        assert infraction.detection == detection
        assert infraction.camera == camera
        assert infraction.recorded_speed_kmh == Decimal("90.0")
        assert infraction.speed_limit_kmh == 60
        assert infraction.status == Infraction.Status.DETECTEE
        evidence = Evidence.objects.get(infraction=infraction)
        assert fake_task.calls == [evidence.id]

    def test_returns_none_when_within_tolerance(self, monkeypatch):
        fake_task = _FakeTask()
        monkeypatch.setattr("apps.anpr.tasks.read_plate_for_evidence", fake_task)
        camera = CameraFactory(speed_limit_kmh=60)
        detection = VehicleDetectionFactory(camera=camera, computed_speed_kmh="63.0")

        result = evaluate_detection_for_infraction(detection, self._exit_frame())

        assert result is None
        assert not Infraction.objects.exists()
        assert fake_task.calls == []

    def test_returns_none_without_exit_frame(self):
        camera = CameraFactory(speed_limit_kmh=60)
        detection = VehicleDetectionFactory(camera=camera, computed_speed_kmh="90.0")

        result = evaluate_detection_for_infraction(detection, None)

        assert result is None
        assert not Infraction.objects.exists()

    @override_settings(SPEED_TOLERANCE_KMH=0)
    def test_boundary_is_strictly_greater_than_limit_plus_tolerance(self, monkeypatch):
        monkeypatch.setattr("apps.anpr.tasks.read_plate_for_evidence", _FakeTask())
        camera = CameraFactory(speed_limit_kmh=60)
        at_limit = VehicleDetectionFactory(camera=camera, computed_speed_kmh="60.0")
        over_limit = VehicleDetectionFactory(camera=camera, computed_speed_kmh="61.0")

        assert evaluate_detection_for_infraction(at_limit, self._exit_frame()) is None
        assert evaluate_detection_for_infraction(over_limit, self._exit_frame()) is not None
