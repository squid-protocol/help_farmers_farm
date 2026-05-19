from django.contrib import admin
from .models import Farm, Crop, WorkCommitment


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ("name", "is_paid", "created_at")
    list_filter = ("is_paid",)

    # NEW: Tell Django it's okay to display this auto-generated field
    readonly_fields = ("created_at",)

    fieldsets = (
        (
            "Core Information",
            {
                "fields": (
                    "name",
                    "created_at",
                    "season_start",
                    "season_end",
                )  # Added here!
            },
        ),
        (
            "Billing & Subscriptions (God Mode)",
            {"fields": ("is_paid", "subscription_tier", "stripe_customer_id")},
        ),
        (
            "Advanced & Onboarding",
            {"fields": ("liability_waiver_text", "onboarding_schema")},
        ),
    )


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("crop_name", "variety", "farm", "category", "is_active")
    list_filter = ("farm", "is_active", "category")
    search_fields = ("crop_name", "variety")


@admin.register(WorkCommitment)
class WorkCommitmentAdmin(admin.ModelAdmin):
    list_display = ("name", "required_hours", "farm")
    list_filter = ("farm",)
    search_fields = ("name",)
