"""Tâche Celery ANPR (CLAUDE.md, pipeline étape 6). Adaptateur fin : toute la
logique métier vit dans apps.anpr.services — jamais de traitement d'image
dans le cycle requête/réponse Django."""

from __future__ import annotations

from celery import shared_task

from apps.anpr.services import create_plate_reading_from_evidence
from apps.infractions.models import Evidence


@shared_task
def read_plate_for_evidence(evidence_id: int) -> int:
    evidence = Evidence.objects.select_related("infraction__detection").get(pk=evidence_id)
    return create_plate_reading_from_evidence(evidence).id
