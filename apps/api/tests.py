from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.infractions.factories import (
    AgentUserFactory,
    EvidenceFactory,
    InfractionFactory,
    SupervisorUserFactory,
    UserFactory,
)
from apps.infractions.models import EvidenceAccessLog, Infraction


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestInfractionViewSet:
    def test_denies_anonymous_access(self, api_client):
        response = api_client.get(reverse("infraction-list"))
        assert response.status_code == 403

    def test_denies_user_without_view_permission(self, api_client):
        api_client.force_authenticate(user=UserFactory())
        response = api_client.get(reverse("infraction-list"))
        assert response.status_code == 403

    def test_agent_can_list_infractions(self, api_client):
        InfractionFactory()
        api_client.force_authenticate(user=AgentUserFactory())

        response = api_client.get(reverse("infraction-list"))

        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_agent_verifies_detectee_infraction(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.DETECTEE)
        api_client.force_authenticate(user=AgentUserFactory())

        response = api_client.post(reverse("infraction-verify", args=[infraction.id]))

        assert response.status_code == 200
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.VERIFIEE

    def test_agent_cannot_validate(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        api_client.force_authenticate(user=AgentUserFactory())

        response = api_client.post(reverse("infraction-validate", args=[infraction.id]))

        assert response.status_code == 403
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.VERIFIEE

    def test_supervisor_validates_verifiee_infraction(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        supervisor = SupervisorUserFactory()
        api_client.force_authenticate(user=supervisor)

        response = api_client.post(reverse("infraction-validate", args=[infraction.id]))

        assert response.status_code == 200
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.VALIDEE
        assert infraction.validated_by == supervisor

    def test_supervisor_rejects_verifiee_infraction(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.VERIFIEE)
        supervisor = SupervisorUserFactory()
        api_client.force_authenticate(user=supervisor)

        response = api_client.post(reverse("infraction-reject", args=[infraction.id]))

        assert response.status_code == 200
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.REJETEE

    def test_invalid_transition_returns_400(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.DETECTEE)
        supervisor = SupervisorUserFactory()
        api_client.force_authenticate(user=supervisor)

        response = api_client.post(reverse("infraction-validate", args=[infraction.id]))

        assert response.status_code == 400
        infraction.refresh_from_db()
        assert infraction.status == Infraction.Status.DETECTEE

    def test_report_returns_pdf_for_validated_infraction(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.VALIDEE)
        EvidenceFactory(infraction=infraction)
        api_client.force_authenticate(user=SupervisorUserFactory())

        response = api_client.get(reverse("infraction-report", args=[infraction.id]))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

    def test_report_rejects_non_validated_infraction(self, api_client):
        infraction = InfractionFactory(status=Infraction.Status.DETECTEE)
        api_client.force_authenticate(user=SupervisorUserFactory())

        response = api_client.get(reverse("infraction-report", args=[infraction.id]))

        assert response.status_code == 400


@pytest.mark.django_db
class TestEvidenceViewSet:
    def test_list_is_not_allowed(self, api_client):
        api_client.force_authenticate(user=AgentUserFactory())

        response = api_client.get(reverse("evidence-list"))

        assert response.status_code == 405

    def test_retrieve_logs_access(self, api_client):
        evidence = EvidenceFactory()
        agent = AgentUserFactory()
        api_client.force_authenticate(user=agent)

        response = api_client.get(reverse("evidence-detail", args=[evidence.id]))

        assert response.status_code == 200
        assert EvidenceAccessLog.objects.filter(evidence=evidence, accessed_by=agent).exists()

    def test_denies_user_without_view_evidence_permission(self, api_client):
        evidence = EvidenceFactory()
        api_client.force_authenticate(user=UserFactory())

        response = api_client.get(reverse("evidence-detail", args=[evidence.id]))

        assert response.status_code == 403
        assert not EvidenceAccessLog.objects.exists()
