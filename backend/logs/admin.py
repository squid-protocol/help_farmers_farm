from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from django.contrib.admin import SimpleListFilter
from .models import LogEntry


# -----------------------------------------------------------------------------
# 0. CUSTOM FILTERS (The Sorting Hat)
# -----------------------------------------------------------------------------
class ShiftLengthFilter(SimpleListFilter):
    """Allows managers to quickly audit potentially erroneous shifts."""

    title = "Shift Length (Audit)"
    parameter_name = "shift_length"

    def lookups(self, request, model_admin):
        return (
            ("short", "Short (< 3 hours)"),
            ("medium", "Standard (3 - 8 hours)"),
            ("long", "⚠️ Suspiciously Long (> 8 hours)"),
        )

    def queryset(self, request, queryset):
        if self.value() == "short":
            return queryset.filter(duration_hours__lt=3)
        if self.value() == "medium":
            return queryset.filter(duration_hours__gte=3, duration_hours__lte=8)
        if self.value() == "long":
            return queryset.filter(duration_hours__gt=8)

        return queryset


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
        "duration_with_audit",
        "activity",
        "crop",
        "get_notes_snippet",
    )

    list_display_links = ("id", "volunteer")
    list_editable = ("activity",)  # Removed duration_hours from editable so our HTML badge renders safely
    list_per_page = 200
    date_hierarchy = "date_logged"
    save_on_top = True

    # CRITICAL: Prevents N+1 query lag when rendering 200 rows at once
    list_select_related = ("volunteer", "farm", "crop")

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    # -------------------------------------------------------------------------
    # 2. FILTERS & SEARCH
    # -------------------------------------------------------------------------
    list_filter = (
        "farm",
        "activity",
        ShiftLengthFilter,
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
    # 3. DETAIL PAGE LAYOUT
    # -------------------------------------------------------------------------
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
                "description": "Immutable timestamp of when this record was physically saved.",
            },
        ),
    )

    # -------------------------------------------------------------------------
    # 4. CUSTOM BULK ACTIONS (God Mode)
    # -------------------------------------------------------------------------
    actions = [
        "calculate_total_hours",
        "bulk_clear_notes",
        "bulk_set_planting",
        "bulk_set_tending",
        "bulk_set_harvesting",
        "bulk_set_cultivating",
        "bulk_set_off_season",
        "bulk_set_move_dirt",
    ]

    @admin.action(description="📊 POWER MOVE: Calculate Total Hours for Selected")
    def calculate_total_hours(self, request, queryset):
        total = queryset.aggregate(total=Sum("duration_hours"))["total"] or 0
        self.message_user(
            request,
            f"The selected {queryset.count()} logs represent a total of {total} hours.",
        )

    @admin.action(description="🧹 BULK ACTION: Scrub / Clear Field Notes")
    def bulk_clear_notes(self, request, queryset):
        updated = queryset.update(notes=None)
        self.message_user(request, f"Successfully scrubbed notes from {updated} logs.")

    @admin.action(description="🌱 BULK ACTION: Change Activity to Planting")
    def bulk_set_planting(self, request, queryset):
        updated = queryset.update(activity="P")
        self.message_user(request, f"Successfully updated {updated} logs to Planting.")

    @admin.action(description="🌿 BULK ACTION: Change Activity to Tending")
    def bulk_set_tending(self, request, queryset):
        updated = queryset.update(activity="T")
        self.message_user(request, f"Successfully updated {updated} logs to Tending.")

    @admin.action(description="🍅 BULK ACTION: Change Activity to Harvesting")
    def bulk_set_harvesting(self, request, queryset):
        updated = queryset.update(activity="H")
        self.message_user(request, f"Successfully updated {updated} logs to Harvesting.")

    @admin.action(description="⛏️ BULK ACTION: Change Activity to Cultivating (Weeding)")
    def bulk_set_cultivating(self, request, queryset):
        updated = queryset.update(activity="C")
        self.message_user(request, f"Successfully updated {updated} logs to Cultivating.")

    @admin.action(description="❄️ BULK ACTION: Change Activity to Off Season Work")
    def bulk_set_off_season(self, request, queryset):
        # Off-season work implies no specific crop, so we safely decouple the crop
        updated = queryset.update(activity="O", crop=None)
        self.message_user(
            request,
            f"Successfully updated {updated} logs to Off Season and cleared invalid crop links.",
        )

    @admin.action(description="🚜 BULK ACTION: Change Activity to Move Dirt")
    def bulk_set_move_dirt(self, request, queryset):
        updated = queryset.update(activity="M", crop=None)
        self.message_user(
            request,
            f"Successfully updated {updated} logs to Move Dirt and cleared invalid crop links.",
        )

    # -------------------------------------------------------------------------
    # 5. CUSTOM CALCULATED METRICS
    # -------------------------------------------------------------------------
    def duration_with_audit(self, obj):
        """Highlights suspiciously long shifts so managers can spot typos."""
        if obj.duration_hours > 8:
            return format_html(
                '<span style="color: #ef4444; font-weight: 900;" title="Requires Audit">{} ⚠️</span>',
                obj.duration_hours,
            )
        return obj.duration_hours

    duration_with_audit.short_description = "Hours"
    duration_with_audit.admin_order_field = "duration_hours"

    def get_notes_snippet(self, obj):
        """Prevents massive note blocks from stretching and breaking the admin table UI."""
        if obj.notes:
            return f"{obj.notes[:45]}..." if len(obj.notes) > 45 else obj.notes
        return "-"

    get_notes_snippet.short_description = "Notes"
