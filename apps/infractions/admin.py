from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.infractions.models import Evidence, EvidenceAccessLog, Infraction


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 0
    readonly_fields = ("sha256_hash", "created_at")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("infractions.view_evidence")


@admin.register(Infraction)
class InfractionAdmin(SimpleHistoryAdmin):
    list_display = (
        "camera",
        "plate",
        "recorded_speed_kmh",
        "speed_limit_kmh",
        "status",
        "validated_by",
        "created_at",
    )
    list_filter = ("status", "camera")
    search_fields = ("plate__normalized_plate",)
    date_hierarchy = "created_at"
    inlines = [EvidenceInline]

    def has_delete_permission(self, request, obj=None):
        # Une infraction n'est jamais supprimée, seulement rejetée.
        return False


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("infraction", "sha256_hash", "created_at")
    readonly_fields = ("sha256_hash", "created_at")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("infractions.view_evidence") and super().has_view_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EvidenceAccessLog)
class EvidenceAccessLogAdmin(admin.ModelAdmin):
    """Journal d'audit des consultations de preuves : lecture seule, jamais
    modifiable ni supprimable (valeur probante de la journalisation elle-même)."""

    list_display = ("evidence", "accessed_by", "accessed_at")
    list_filter = ("accessed_by",)
    date_hierarchy = "accessed_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
