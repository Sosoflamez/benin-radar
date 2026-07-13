import hashlib
import io

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from PIL import Image

from apps.infractions.admin import EvidenceAdmin, InfractionAdmin
from apps.infractions.factories import InfractionFactory
from apps.infractions.models import Evidence, Infraction
from apps.infractions.services import create_evidence


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
