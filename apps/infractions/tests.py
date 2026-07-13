import hashlib
import io
from decimal import Decimal

import numpy as np
import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from PIL import Image

from apps.cameras.factories import CameraFactory
from apps.detection.factories import VehicleDetectionFactory
from apps.infractions.admin import EvidenceAdmin, InfractionAdmin
from apps.infractions.factories import (
    AgentUserFactory,
    EvidenceFactory,
    InfractionFactory,
    SupervisorUserFactory,
    UserFactory,
)
from apps.infractions.models import Evidence, EvidenceAccessLog, Infraction
from apps.infractions.reports import generate_infraction_report_pdf
from apps.infractions.services import (
    create_evidence,
    evaluate_detection_for_infraction,
    log_evidence_access,
    transition_to_rejected,
    transition_to_validated,
    transition_to_verified,
)


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
            "verify_infraction",
        }


@pytest.mark.django_db
class TestSupervisorsGroup:
    def test_created_by_migration_with_expected_permissions(self):
        group = Group.objects.get(name="Superviseurs")
        codenames = set(group.permissions.values_list("codename", flat=True))
        assert codenames == {
            "view_plate_data",
            "view_evidence",
            "view_infraction",
            "verify_infraction",
            "validate_infraction",
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


@pytest.mark.django_db
class TestTransitionToVerified:
    def test_agent_moves_detectee_to_verifiee(self):
        infraction = InfractionFactory(status=Infraction.Status.DETECTEE)
        agent = AgentUserFactory()

        result = transition_to_verified(infraction, agent)

        assert result.status == Infraction.Status.VERIFIEE
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.VERIFIEE

    def test_denies_user_without_verify_permission(self):
        infraction = InfractionFactory(status=Infraction.Status.DETECTEE)
        outsider = UserFactory()

        with pytest.raises(PermissionDenied):
            transition_to_verified(infraction, outsider)
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.DETECTEE

    def test_rejects_transition_from_non_detectee_status(self):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        agent = AgentUserFactory()

        with pytest.raises(ValidationError):
            transition_to_verified(infraction, agent)


@pytest.mark.django_db
class TestTransitionToValidatedOrRejected:
    def test_supervisor_moves_verifiee_to_validee(self):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        supervisor = SupervisorUserFactory()

        result = transition_to_validated(infraction, supervisor)

        assert result.status == Infraction.Status.VALIDEE
        assert result.validated_by == supervisor

    def test_supervisor_moves_verifiee_to_rejetee(self):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        supervisor = SupervisorUserFactory()

        result = transition_to_rejected(infraction, supervisor)

        assert result.status == Infraction.Status.REJETEE
        assert result.validated_by == supervisor

    def test_denies_agent_without_validate_permission(self):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        agent = AgentUserFactory()

        with pytest.raises(PermissionDenied):
            transition_to_validated(infraction, agent)

    def test_rejects_transition_from_non_verifiee_status(self):
        infraction = InfractionFactory(status=Infraction.Status.DETECTEE)
        supervisor = SupervisorUserFactory()

        with pytest.raises(ValidationError):
            transition_to_validated(infraction, supervisor)


@pytest.mark.django_db
class TestLogEvidenceAccess:
    def test_creates_log_entry_for_authorized_user(self):
        evidence = EvidenceFactory()
        agent = AgentUserFactory()

        log = log_evidence_access(evidence, agent)

        assert isinstance(log, EvidenceAccessLog)
        assert log.evidence == evidence
        assert log.accessed_by == agent
        assert EvidenceAccessLog.objects.filter(evidence=evidence, accessed_by=agent).exists()

    def test_denies_user_without_view_evidence_permission(self):
        evidence = EvidenceFactory()
        outsider = UserFactory()

        with pytest.raises(PermissionDenied):
            log_evidence_access(evidence, outsider)
        assert not EvidenceAccessLog.objects.exists()


@pytest.mark.django_db
class TestGenerateInfractionReportPdf:
    def test_denies_user_without_required_permissions(self):
        infraction = InfractionFactory(status=Infraction.Status.VALIDEE)
        outsider = UserFactory()

        with pytest.raises(PermissionDenied):
            generate_infraction_report_pdf(infraction, outsider)

    def test_rejects_non_validated_infraction(self):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        supervisor = SupervisorUserFactory()

        with pytest.raises(ValidationError):
            generate_infraction_report_pdf(infraction, supervisor)

    def test_returns_pdf_bytes_for_validated_infraction(self):
        infraction = InfractionFactory(status=Infraction.Status.VALIDEE)
        EvidenceFactory(infraction=infraction)
        supervisor = SupervisorUserFactory()

        pdf_bytes = generate_infraction_report_pdf(infraction, supervisor)

        assert pdf_bytes.startswith(b"%PDF")
