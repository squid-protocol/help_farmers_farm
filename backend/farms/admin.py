from django.contrib import admin
from django.utils import timezone
from .models import Farm, Crop, WorkCommitment, ComplianceForm, FarmProfile, FarmImage


# -----------------------------------------------------------------------------
# 1. INLINES: Edit connected database rows directly from the Farm page
# -----------------------------------------------------------------------------
class FarmProfileInline(admin.StackedInline):
    """Allows superusers to toggle public directory visibility directly from the Farm."""

    model = FarmProfile
    can_delete = False
    max_num = 1
    classes = ("collapse",)


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
    actions = [
        "reset_trial_period",
        "grant_lifetime_access",
        "mark_as_paid",
        "revoke_premium",
        "enable_joint_accounts",
        "disable_joint_accounts",
    ]

    @admin.action(description="BULK ACTION: Reset 60-Day Free Trial")
    def reset_trial_period(self, request, queryset):
        queryset.update(created_at=timezone.now())
        self.message_user(
            request, "Selected farms have had their 60-day trials reset to today."
        )

    @admin.action(description="BULK ACTION: Grant Lifetime Free Access (Comped)")
    def grant_lifetime_access(self, request, queryset):
        queryset.update(is_comped=True, is_paid=True)
        self.message_user(request, "Selected farms granted lifetime comped access.")

    @admin.action(description="BULK ACTION: Mark as Paid")
    def mark_as_paid(self, request, queryset):
        queryset.update(is_paid=True)
        self.message_user(request, "Selected farms marked as paid.")

    @admin.action(description="BULK ACTION: Revoke Premium Access (Mark Unpaid)")
    def revoke_premium(self, request, queryset):
        queryset.update(is_paid=False, is_comped=False)
        self.message_user(
            request, "Premium access revoked. Farms returned to read-only/trial state."
        )

    @admin.action(
        description="BULK ACTION: Enable Joint Accounts (Disable strict liability)"
    )
    def enable_joint_accounts(self, request, queryset):
        queryset.update(allows_joint_accounts=True)
        self.message_user(request, "Joint accounts enabled for selected farms.")

    @admin.action(
        description="BULK ACTION: Disable Joint Accounts (Enforce strict liability)"
    )
    def disable_joint_accounts(self, request, queryset):
        queryset.update(allows_joint_accounts=False)
        self.message_user(request, "Strict liability enforced for selected farms.")

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

    inlines = [
        FarmProfileInline,
        WorkCommitmentInline,
        CropInline,
        ComplianceFormInline,
    ]

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

    actions = ["bulk_activate", "bulk_deactivate", "clear_expirations"]

    @admin.action(description="BULK ACTION: Activate selected legal forms")
    def bulk_activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Successfully activated {updated} forms.")

    @admin.action(description="BULK ACTION: Archive (Deactivate) selected legal forms")
    def bulk_deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Successfully archived {updated} forms.")

    @admin.action(description="BULK ACTION: Clear expirations (Set to never expire)")
    def clear_expirations(self, request, queryset):
        updated = queryset.update(does_expire=False, expiration_date=None)
        self.message_user(request, f"Cleared expiration dates for {updated} forms.")

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


# -----------------------------------------------------------------------------
# 5. GLOBAL DIRECTORY SWITCHBOARD
# -----------------------------------------------------------------------------
@admin.register(FarmProfile)
class FarmProfileAdmin(admin.ModelAdmin):
    """A master switchboard to manage public visibility for all farms at once."""

    list_display = ("farm", "is_public", "is_accepting_volunteers", "short_description")
    list_display_links = ("farm",)

    # This allows you to toggle 100 farms to public/private right from the list view
    list_editable = ("is_public", "is_accepting_volunteers", "short_description")
    list_per_page = 200
    save_on_top = True
    list_select_related = ("farm",)

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = ("is_public", "is_accepting_volunteers")
    search_fields = ("farm__name", "short_description", "tags")
    autocomplete_fields = ["farm"]

    actions = ["make_public", "make_private", "open_applications", "close_applications"]

    @admin.action(description="BULK ACTION: Publish to Public Directory")
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f"Published {updated} farms to the directory.")

    @admin.action(description="BULK ACTION: Hide from Public Directory")
    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f"Hid {updated} farms from the directory.")

    @admin.action(description="BULK ACTION: Open for Volunteer Applications")
    def open_applications(self, request, queryset):
        updated = queryset.update(is_accepting_volunteers=True)
        self.message_user(request, f"Opened applications for {updated} farms.")

    @admin.action(description="BULK ACTION: Close Volunteer Applications")
    def close_applications(self, request, queryset):
        updated = queryset.update(is_accepting_volunteers=False)
        self.message_user(request, f"Closed applications for {updated} farms.")


@admin.register(FarmImage)
class FarmImageAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "uploaded_at")
    list_filter = ("profile__farm", "uploaded_at")
