from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.anpr.models import PlateReading


@admin.register(PlateReading)
class PlateReadingAdmin(SimpleHistoryAdmin):
    list_display = ("normalized_plate", "status", "ocr_confidence", "detection", "created_at")
    list_filter = ("status",)
    search_fields = ("normalized_plate", "raw_plate")
    date_hierarchy = "created_at"

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("anpr.view_plate_data") and super().has_view_permission(
            request, obj
        )
