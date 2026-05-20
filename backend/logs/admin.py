from django.contrib import admin
from .models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Global master ledger of every single hour logged across the platform."""

    # What you see on the main list page
    list_display = (
        "volunteer",
        "farm",
        "date_logged",
        "duration_hours",
        "activity",
        "crop",
        "get_notes_snippet",
    )

    # Sidebar filters for slicing data
    list_filter = (
        "farm",
        "date_logged",
        "activity",
    )

    # Search bar targets
    search_fields = (
        "volunteer__username",
        "volunteer__first_name",
        "volunteer__last_name",
        "farm__name",
        "crop__crop_name",
        "notes",
    )

    # CRITICAL: Changes massive, page-crashing dropdowns into highly optimized search bars
    autocomplete_fields = ["volunteer", "farm", "crop"]

    readonly_fields = ("created_at",)

    # Organize the actual detail page into beautiful, logical blocks
    fieldsets = (
        (
            "Identity & Location",
            {"fields": ("volunteer", "farm"), "description": "Who worked and where."},
        ),
        (
            "Shift Details",
            {
                "fields": ("date_logged", "duration_hours", "activity", "crop"),
            },
        ),
        (
            "Context",
            {
                "fields": ("notes",),
                "description": "Optional details provided by the volunteer about their shift.",
            },
        ),
        (
            "System Metadata",
            {
                "fields": ("created_at",),
                "classes": ("collapse",),
                "description": "Immutable timestamp of when this record was physically saved to the database.",
            },
        ),
    )

    # -------------------------------------------------------------------------
    # CUSTOM CALCULATED METRICS & FORMATTERS
    # -------------------------------------------------------------------------
    def get_notes_snippet(self, obj):
        """Prevents massive note blocks from stretching and breaking the admin table UI."""
        if obj.notes:
            return f"{obj.notes[:45]}..." if len(obj.notes) > 45 else obj.notes
        return "-"

    get_notes_snippet.short_description = "Notes"
