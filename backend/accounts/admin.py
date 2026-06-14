from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, FarmMembership, FormSignature


# -----------------------------------------------------------------------------
# 1. INLINES: See connected data directly on the User Profile
# -----------------------------------------------------------------------------
class FarmMembershipInline(admin.TabularInline):
    """Allows admins to see and manage which farms a user belongs to."""

    model = FarmMembership
    extra = 0  # Don't clutter the UI with blank rows
    fields = ("farm", "work_commitment", "is_approved", "agreed_to_waiver")
    autocomplete_fields = ["farm"]  # Makes it easy to search if you have 100+ farms


class FormSignatureInline(admin.TabularInline):
    """
    Displays the user's signed legal waivers.
    Crucially, these are READ-ONLY to protect the WORM audit log integrity.
    """

    model = FormSignature
    extra = 0
    can_delete = False  # Do not allow accidental deletion of legal records

    # Lock down the fields so they can be viewed but never edited
    readonly_fields = (
        "form",
        "digital_signature",
        "signed_at",
        "is_guardian_signature",
        "signer_ip_address",
        "document_hash",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        """Prevent manually forging signatures from the Admin dashboard."""
        return False


# -----------------------------------------------------------------------------
# 2. MASTER USER ADMIN
# -----------------------------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "get_associated_farms",
        "role",
        "get_waiver_status",
        "is_email_verified",
        "is_active",
    )

    list_display_links = ("username", "first_name", "last_name")

    # NEW: The Spreadsheet Mode
    list_editable = ("role", "is_email_verified", "is_active")
    list_per_page = 200
    save_on_top = True
    date_hierarchy = "date_joined"

    # NEW: High Density CSS Injection
    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = (
        "memberships__farm",
        "memberships__agreed_to_waiver",
        "role",
        "is_email_verified",
        "is_active",
    )
    search_fields = ("username", "first_name", "last_name", "email", "phone_number")

    inlines = [FarmMembershipInline, FormSignatureInline]

    actions = [
        "mark_email_verified",
        "mark_as_legacy_friend",
        "mark_as_active_volunteer",
        "bulk_deactivate_users",
        "bulk_activate_users",
    ]

    @admin.action(description="📧 BULK ACTION: Mark selected as Email Verified")
    def mark_email_verified(self, request, queryset):
        updated = queryset.update(is_email_verified=True)
        self.message_user(request, f"Successfully verified {updated} users.")

    @admin.action(description="📉 BULK ACTION: Downgrade Role to Friend (Legacy)")
    def mark_as_legacy_friend(self, request, queryset):
        updated = queryset.update(role="friend")
        self.message_user(request, f"Successfully changed {updated} users to Friend.")

    @admin.action(description="📈 BULK ACTION: Upgrade Role to Active Volunteer")
    def mark_as_active_volunteer(self, request, queryset):
        updated = queryset.update(role="volunteer")
        self.message_user(
            request, f"Successfully changed {updated} users to Active Volunteer."
        )

    @admin.action(description="🛑 POWER MOVE: Deactivate (Lock Out) Users")
    def bulk_deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Successfully locked out {updated} users.")

    @admin.action(description="✅ POWER MOVE: Activate Users")
    def bulk_activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Successfully activated {updated} users.")

    @admin.display(description="Farms")
    def get_associated_farms(self, obj):
        farms = [m.farm.name for m in obj.memberships.all()]
        return ", ".join(farms)

    @admin.display(description="Waiver Checkbox", boolean=True)
    def get_waiver_status(self, obj):
        return obj.memberships.filter(agreed_to_waiver=True).exists()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("memberships__farm")

    fieldsets = UserAdmin.fieldsets + (
        (
            "Contact & Identity",
            {
                "fields": (
                    "phone_number",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "avatar",
                )
            },
        ),
        (
            "Platform Access & Compliance",
            {
                "fields": ("role", "is_email_verified", "legacy_years_volunteered"),
                "description": "Manage the user's permission level and compliance status.",
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Custom App Details",
            {
                "fields": (
                    "role",
                    "phone_number",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "is_email_verified",
                )
            },
        ),
    )


# -----------------------------------------------------------------------------
# 3. GLOBAL MEMBERSHIP BRIDGE
# -----------------------------------------------------------------------------
@admin.register(FarmMembership)
class FarmMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "farm",
        "work_commitment",
        "is_approved",
    )

    list_display_links = ("id", "user")

    # NEW: The Spreadsheet Mode
    list_editable = ("work_commitment", "is_approved")
    list_per_page = 200
    save_on_top = True

    # NEW: SQL Optimizer for mass list views
    list_select_related = ("user", "farm", "work_commitment")

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = ("farm", "is_approved", "work_commitment")
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "farm__name",
    )
    autocomplete_fields = ["user", "farm"]

    actions = [
        "bulk_approve",
        "bulk_revoke",
        "bulk_waiver_bypass",
    ]

    @admin.action(description="✅ BULK ACTION: Approve Pending Roster Applications")
    def bulk_approve(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(
            request, f"Approved {updated} volunteer applications across the platform."
        )

    @admin.action(description="🛑 BULK ACTION: Revoke Approvals (Suspend)")
    def bulk_revoke(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"Revoked approval for {updated} memberships.")

    @admin.action(description="⚠️ POWER MOVE: Manually Override/Bypass Legal Waiver")
    def bulk_waiver_bypass(self, request, queryset):
        updated = queryset.update(agreed_to_waiver=True)
        self.message_user(
            request,
            f"Bypassed waiver requirements for {updated} memberships. WARNING: This circumvents the WORM audit log.",
        )


# -----------------------------------------------------------------------------
# 4. WORM AUDIT LOG (LEGAL VAULT)
# -----------------------------------------------------------------------------
@admin.register(FormSignature)
class FormSignatureAdmin(admin.ModelAdmin):
    """
    A dedicated, highly-restricted vault for viewing all legal signatures globally.
    No mass actions are permitted here by design to preserve audit integrity.
    """

    list_display = (
        "user",
        "get_farm_name",
        "form",
        "digital_signature",
        "signed_at",
        "has_pdf",
    )

    # NEW: Vault Optimizations
    list_per_page = 200
    date_hierarchy = "signed_at"
    list_select_related = ("user", "form", "form__farm")

    class Media:
        css = {"all": ("css/admin_dense.css",)}

    list_filter = ("form__farm", "signed_at", "is_guardian_signature")
    search_fields = (
        "user__username",
        "user__email",
        "digital_signature",
        "document_hash",
        "signer_ip_address",
    )

    readonly_fields = (
        "user",
        "form",
        "digital_signature",
        "signed_at",
        "is_guardian_signature",
        "guardian_relationship",
        "signer_ip_address",
        "document_hash",
        "pdf_receipt",
    )

    fieldsets = (
        ("Signer Information", {"fields": ("user", "digital_signature", "signed_at")}),
        ("Document Details", {"fields": ("form",)}),
        (
            "Guardian Override (If Applicable)",
            {
                "fields": ("is_guardian_signature", "guardian_relationship"),
            },
        ),
        (
            "WORM Cryptographic Data",
            {
                "fields": ("signer_ip_address", "document_hash", "pdf_receipt"),
                "description": "Immutable proof of signature. Do not attempt to alter.",
            },
        ),
    )

    def get_farm_name(self, obj):
        return obj.form.farm.name

    get_farm_name.short_description = "Farm"
    get_farm_name.admin_order_field = "form__farm__name"

    def has_pdf(self, obj):
        """Visual check to ensure the asynchronous PDF worker successfully generated the file."""
        return bool(obj.pdf_receipt)

    has_pdf.boolean = True
    has_pdf.short_description = "PDF Generated"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
