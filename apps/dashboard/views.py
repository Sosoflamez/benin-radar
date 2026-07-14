from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from apps.dashboard.services import _serialize_infraction
from apps.infractions.models import Infraction

RECENT_INFRACTIONS_LIMIT = 50


class InfractionsLiveView(LoginRequiredMixin, ListView):
    """Flux d'infractions récentes, mis à jour en direct via ws/infractions/."""

    model = Infraction
    template_name = "dashboard/infractions_live.html"
    context_object_name = "infractions"

    def get_queryset(self):
        return Infraction.objects.select_related("camera").order_by("-created_at")[
            :RECENT_INFRACTIONS_LIMIT
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Même forme que ce que InfractionConsumer pousse en direct, pour
        # qu'Alpine.js n'ait qu'un seul format à interpréter côté client.
        context["infractions_json"] = [
            _serialize_infraction(infraction) for infraction in context["infractions"]
        ]
        return context
