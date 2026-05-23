from django.contrib import admin
from django.utils import timezone
from .models import Farm, Crop, WorkCommitment, ComplianceForm


# -----------------------------------------------------------------------------
# 1. INLINES: Edit connected database rows directly from the Farm page
# -----------------------------------------------------------------------------
class CropInline(admin.TabularInline):
    model = Crop
    extra = 0  # Don't show empty rows by default
    fields = ("crop_name", "variety", "category", "is_active")


class WorkCommitmentInline(admin.TabularInline):
    model = WorkCommitment
    extra = 0
    fields = ("name", "required_hours", "symbol")


class ComplianceFormInline(admin.StackedInline):
    """Stacked is better here because the legal text body is huge."""

    model = ComplianceForm
    extra = 0
    fields = (
        "name",
        "is_active",
        "assignment_type",
        "does_expire",
        "expiration_date",
        "body_text",
    )
    classes = ("collapse",)  # Keeps the UI clean by collapsing them by default


# -----------------------------------------------------------------------------
# 2. THE MASTER FARM ADMIN
# -----------------------------------------------------------------------------
@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    actions = ["reset_trial_period", "grant_lifetime_access", "mark_as_paid"]

    @admin.action(description="BULK ACTION: Reset 60-Day Free Trial")
    def reset_trial_period(self, request, queryset):
        queryset.update(created_at=timezone.now())
        self.message_user(
            request, "Selected farms have had their 60-day trials reset to today."
        )

    @admin.action(description="BULK ACTION: Grant Lifetime Free Access (Comped)")
    def grant_lifetime_access(self, request, queryset):
        queryset.update(is_comped=True)
        self.message_user(request, "Selected farms granted lifetime comped access.")

    @admin.action(description="BULK ACTION: Mark as Paid")
    def mark_as_paid(self, request, queryset):
        queryset.update(is_paid=True)
        self.message_user(request, "Selected farms marked as paid.")

    list_display = (
        "id",
        "name",
        "account_number",
        "get_active_forms_count",
        "allows_joint_accounts",
        "is_paid",
        "is_comped",
    )

    list_display_links = ("id", "name", "account_number")
    list_editable = ("allows_joint_accounts", "is_paid", "is_comped")
    list_per_page = 200
    save_on_top = True
    date_hierarchy = "created_at"

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = (
        "is_paid",
        "allows_joint_accounts",
        "created_at",
        "subscription_tier",
    )
    search_fields = ("name", "account_number", "contact_email")

    readonly_fields = (
        "account_number",
        "get_active_forms_count",
        "get_volunteer_count",
    )

    inlines = [WorkCommitmentInline, CropInline, ComplianceFormInline]

    fieldsets = (
        (
            "Identity & Contact",
            {
                "fields": (
                    "name",
                    "account_number",
                    "contact_email",
                    "phone_number",
                    "address",
                )
            },
        ),
        ("Season & Operations", {"fields": ("season_start", "season_end")}),
        (
            "Compliance & Onboarding",
            {
                "fields": (
                    "allows_joint_accounts",
                    "onboarding_schema",
                    "get_active_forms_count",
                    "get_volunteer_count",
                ),
                "description": "Manage legacy account exceptions and view real-time compliance metrics.",
            },
        ),
        (
            "Billing & Subscriptions (God Mode)",
            {
                "fields": (
                    "is_paid",
                    "is_comped",
                    "subscription_tier",
                    "stripe_customer_id",
                    "created_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # -------------------------------------------------------------------------
    # 3. CUSTOM CALCULATED METRICS
    # -------------------------------------------------------------------------
    def get_active_forms_count(self, obj):
        """Calculates how many active waivers are currently required by this farm."""
        count = obj.compliance_forms.filter(is_active=True).count()
        return f"{count} Active Forms"

    get_active_forms_count.short_description = "Active Waivers"

    def get_volunteer_count(self, obj):
        """Cross-references the accounts app to count active roster members."""
        count = obj.memberships.filter(is_approved=True).count()
        return f"{count} Approved Volunteers"

    get_volunteer_count.short_description = "Roster Size"


# -----------------------------------------------------------------------------
# 4. GLOBAL STANDALONE VIEWS
# -----------------------------------------------------------------------------
@admin.register(ComplianceForm)
class ComplianceFormAdmin(admin.ModelAdmin):
    """Global view of all legal documents across all farms."""

    list_display = (
        "id",
        "name",
        "farm",
        "is_active",
        "assignment_type",
        "does_expire",
        "expiration_date",
    )

    list_display_links = ("id", "name")
    list_editable = ("is_active", "assignment_type", "does_expire", "expiration_date")
    list_per_page = 200
    save_on_top = True
    list_select_related = ("farm",)

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = ("farm", "is_active", "assignment_type", "does_expire")
    search_fields = ("name", "farm__name", "body_text")
    autocomplete_fields = ["farm", "assigned_users"]

    fieldsets = (
        ("Document Info", {"fields": ("farm", "name", "is_active")}),
        ("Legal Text", {"fields": ("body_text",)}),
        (
            "Targeting Engine",
            {
                "fields": ("assignment_type", "assigned_users"),
                "description": "Determines who is required to sign this specific waiver.",
            },
        ),
        ("Expiration Rules", {"fields": ("does_expire", "expiration_date")}),
    )


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    """Global dictionary of all crops."""

    list_display = ("id", "crop_name", "variety", "farm", "category", "is_active")

    list_display_links = ("id", "crop_name")
    list_editable = ("variety", "category", "is_active")
    list_per_page = 200
    save_on_top = True
    list_select_related = ("farm",)

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = ("farm", "category", "is_active")
    search_fields = ("crop_name", "variety", "farm__name")
    autocomplete_fields = ["farm"]

    actions = ["bulk_activate", "bulk_deactivate"]

    @admin.action(description="BULK ACTION: Activate selected crops")
    def bulk_activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Successfully activated {updated} crops.")

    @admin.action(description="BULK ACTION: Deactivate (Archive) selected crops")
    def bulk_deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Successfully archived {updated} crops.")


@admin.register(WorkCommitment)
class WorkCommitmentAdmin(admin.ModelAdmin):
    """Global view of all membership/commitment tiers."""

    list_display = ("id", "name", "farm", "required_hours", "symbol")

    list_display_links = ("id", "name")
    list_editable = ("required_hours", "symbol")
    list_per_page = 200
    save_on_top = True
    list_select_related = ("farm",)

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = ("farm",)
    search_fields = ("name", "farm__name")
    autocomplete_fields = ["farm"]
