from __future__ import annotations

from rest_framework import serializers

from apps.infractions.models import Evidence, Infraction


class InfractionSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)
    plate_normalized = serializers.CharField(
        source="plate.normalized_plate", read_only=True, default=""
    )
    validated_by_username = serializers.CharField(
        source="validated_by.username", read_only=True, default=""
    )

    class Meta:
        model = Infraction
        fields = [
            "id",
            "camera",
            "camera_name",
            "plate",
            "plate_normalized",
            "recorded_speed_kmh",
            "speed_limit_kmh",
            "status",
            "validated_by",
            "validated_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = [
            "id",
            "infraction",
            "full_image",
            "plate_crop_image",
            "sha256_hash",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
