"""Endpoints DRF /api/v1/ (CLAUDE.md). Adaptateurs fins : toute la logique de
permission et de transition du workflow de validation agent vit dans
apps.infractions.services — voir CLAUDE.md, tâches en instance Phase 4."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.exceptions import PermissionDenied as DrfPermissionDenied
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api.permissions import HasEvidenceViewPermission, HasInfractionViewPermission
from apps.api.serializers import EvidenceSerializer, InfractionSerializer
from apps.infractions import services
from apps.infractions.models import Evidence, Infraction
from apps.infractions.reports import generate_infraction_report_pdf


class InfractionViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des infractions et transitions du workflow de
    validation : `verify` (agent, detectee -> verifiee) puis `validate` ou
    `reject` (superviseur, verifiee -> validee/rejetee)."""

    queryset = Infraction.objects.select_related("camera", "plate", "validated_by")
    serializer_class = InfractionSerializer
    permission_classes = [IsAuthenticated, HasInfractionViewPermission]

    def _apply_transition(self, request, transition) -> Response:
        infraction = self.get_object()
        try:
            transition(infraction, request.user)
        except DjangoPermissionDenied as exc:
            raise DrfPermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            raise DrfValidationError(exc.messages) from exc
        return Response(self.get_serializer(infraction).data)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None) -> Response:
        return self._apply_transition(request, services.transition_to_verified)

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None) -> Response:
        return self._apply_transition(request, services.transition_to_validated)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None) -> Response:
        return self._apply_transition(request, services.transition_to_rejected)

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None) -> HttpResponse:
        infraction = self.get_object()
        try:
            pdf_bytes = generate_infraction_report_pdf(infraction, request.user)
        except DjangoPermissionDenied as exc:
            raise DrfPermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            raise DrfValidationError(exc.messages) from exc
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="infraction-{infraction.id}.pdf"'
        return response


class EvidenceViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des preuves, une par une seulement (pas de `list`, qui
    permettrait une consultation en masse non journalisée individuellement).
    Chaque `retrieve` est journalisé via
    apps.infractions.services.log_evidence_access."""

    queryset = Evidence.objects.select_related("infraction")
    serializer_class = EvidenceSerializer
    permission_classes = [IsAuthenticated, HasEvidenceViewPermission]

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "GET", detail="Consultation individuelle uniquement (GET /evidences/{id}/)."
        )

    def retrieve(self, request, *args, **kwargs) -> Response:
        evidence: Evidence = self.get_object()
        try:
            services.log_evidence_access(evidence, request.user)
        except DjangoPermissionDenied as exc:
            raise DrfPermissionDenied(str(exc)) from exc
        return Response(self.get_serializer(evidence).data)
