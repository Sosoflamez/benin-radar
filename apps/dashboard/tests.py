import pytest
from django.urls import reverse

from apps.infractions.factories import AgentUserFactory, InfractionFactory


@pytest.mark.django_db
class TestInfractionsLiveView:
    def test_anonymous_user_is_redirected_to_login(self, client):
        response = client.get(reverse("dashboard-home"))

        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_agent_sees_recent_infractions(self, client):
        agent = AgentUserFactory()
        infraction = InfractionFactory()
        client.force_login(agent)

        response = client.get(reverse("dashboard-home"))

        assert response.status_code == 200
        assert infraction in response.context["infractions"]
        assert response.context["infractions_json"][0]["id"] == infraction.id
