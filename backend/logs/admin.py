from django.contrib import admin
from .models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Global master ledger of every single hour logged across the platform."""

    # -------------------------------------------------------------------------
    # 1. THE SPREADSHEET VIEW (High Density)
    # -------------------------------------------------------------------------
    list_display = (
        "id",
        "volunteer",
        "farm",
        "date_logged",
        "duration_hours",
        "activity",
        "crop",
        "get_notes_snippet",
    )

    list_display_links = ("id", "volunteer")
    list_editable = ("duration_hours", "activity")
    list_per_page = 200
    date_hierarchy = "date_logged"
    save_on_top = True

    # CRITICAL: Prevents N+1 query lag when rendering 200 rows at once
    list_select_related = ("volunteer", "farm", "crop")

    # -------------------------------------------------------------------------
    # 2. CSS INJECTION (The Squish)
    # -------------------------------------------------------------------------
    class Media:
        css = {"all": ("css/admin_dense.css",)}

    # -------------------------------------------------------------------------
    # 3. FILTERS & SEARCH
    # -------------------------------------------------------------------------
    list_filter = (
        "farm",
        "activity",
        "date_logged",
    )

    search_fields = (
        "volunteer__username",
        "volunteer__first_name",
        "volunteer__last_name",
        "farm__name",
        "crop__crop_name",
        "notes",
    )

    autocomplete_fields = ["volunteer", "farm", "crop"]
    readonly_fields = ("created_at",)

    # -------------------------------------------------------------------------
    # 4. DETAIL PAGE LAYOUT
    # -------------------------------------------------------------------------
    # Transforms the activity dropdown into a fast, horizontal radio button array
    radio_fields = {"activity": admin.HORIZONTAL}

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
    # 5. CUSTOM BULK ACTIONS
    # -------------------------------------------------------------------------
    actions = ["bulk_set_planting", "bulk_set_tending", "bulk_set_harvesting"]

    @admin.action(description="BULK ACTION: Change Activity to Planting")
    def bulk_set_planting(self, request, queryset):
        updated = queryset.update(activity="P")
        self.message_user(request, f"Successfully updated {updated} logs to Planting.")

    @admin.action(description="BULK ACTION: Change Activity to Tending")
    def bulk_set_tending(self, request, queryset):
        updated = queryset.update(activity="T")
        self.message_user(request, f"Successfully updated {updated} logs to Tending.")

    @admin.action(description="BULK ACTION: Change Activity to Harvesting")
    def bulk_set_harvesting(self, request, queryset):
        updated = queryset.update(activity="H")
        self.message_user(
            request, f"Successfully updated {updated} logs to Harvesting."
        )

    # -------------------------------------------------------------------------
    # 6. CUSTOM CALCULATED METRICS
    # -------------------------------------------------------------------------
    def get_notes_snippet(self, obj):
        """Prevents massive note blocks from stretching and breaking the admin table UI."""
        if obj.notes:
            return f"{obj.notes[:45]}..." if len(obj.notes) > 45 else obj.notes
        return "-"

    get_notes_snippet.short_description = "Notes"
