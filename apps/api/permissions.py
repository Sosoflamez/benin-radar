"""Permissions DRF pour l'API versionnée /api/v1/ (CLAUDE.md). Les
transitions de statut et la journalisation des consultations restent
vérifiées dans apps.infractions.services — ces classes ne font que garder
les accès en lecture (list/retrieve) hors des mains d'un utilisateur sans
permission dédiée."""

from __future__ import annotations

from rest_framework.permissions import BasePermission


class HasInfractionViewPermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_perm("infractions.view_infraction")


class HasEvidenceViewPermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.has_perm("infractions.view_evidence")
