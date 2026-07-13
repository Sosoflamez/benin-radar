"""Génération de rapports PDF d'infraction (Phase 5, durcissement).
Réservé aux infractions validées : un rapport n'a de valeur probante que
pour une décision déjà tranchée par un superviseur (CLAUDE.md, workflow
detectee -> verifiee -> validee/rejetee)."""

from __future__ import annotations

import io

from django.core.exceptions import PermissionDenied, ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from apps.anpr.models import PlateReading
from apps.infractions.models import Infraction


def _plate_label(infraction: Infraction) -> str:
    plate = infraction.plate
    if plate is None or plate.status != PlateReading.Status.LISIBLE:
        return "illisible"
    return plate.normalized_plate


def generate_infraction_report_pdf(infraction: Infraction, user) -> bytes:
    """Construit le PDF en mémoire (jamais écrit sur disque ici — c'est à
    l'appelant de décider de la persistance ou du téléchargement direct)."""
    if not user.has_perm("infractions.view_infraction") or not user.has_perm(
        "infractions.view_evidence"
    ):
        raise PermissionDenied("Permission de consultation des infractions et des preuves requise.")
    if infraction.status != Infraction.Status.VALIDEE:
        raise ValidationError("Seule une infraction validée peut être exportée en rapport PDF.")

    evidence = infraction.evidences.order_by("created_at").first()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, "Rapport d'infraction — Benin-radar")
    y -= 1.2 * cm

    pdf.setFont("Helvetica", 11)
    lines = [
        f"Infraction n° {infraction.id}",
        f"Caméra : {infraction.camera.name}",
        f"Date de détection : {infraction.created_at:%Y-%m-%d %H:%M:%S}",
        f"Vitesse retenue : {infraction.recorded_speed_kmh} km/h",
        f"Limite autorisée : {infraction.speed_limit_kmh} km/h",
        f"Plaque : {_plate_label(infraction)}",
        f"Statut : {infraction.get_status_display()}",
        f"Validé par : {infraction.validated_by}",
    ]
    for text in lines:
        pdf.drawString(2 * cm, y, text)
        y -= 0.7 * cm

    if evidence is not None:
        pdf.setFont("Helvetica", 9)
        pdf.drawString(2 * cm, y, f"Hash SHA-256 de la preuve : {evidence.sha256_hash}")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
