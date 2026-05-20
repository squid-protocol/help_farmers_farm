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
        "email",
        "first_name",
        "last_name",
        "role",
        "is_email_verified",
        "is_active",
    )

    list_filter = ("role", "is_email_verified", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email", "phone_number")

    # Inject the Farm connections and the Legal Signatures directly into the profile
    inlines = [FarmMembershipInline, FormSignatureInline]

    # Reorganize the profile layout to expose all the new compliance fields
    fieldsets = UserAdmin.fieldsets + (
        (
            "Contact & Identity",
            {"fields": ("phone_number", "address", "avatar")},
        ),
        (
            "Platform Access & Compliance",
            {
                "fields": ("role", "is_email_verified", "legacy_years_volunteered"),
                "description": "Manage the user's permission level and compliance status.",
            },
        ),
    )

    # Required for when you manually click "Add User" in the admin
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Custom App Details",
            {"fields": ("role", "phone_number", "address", "is_email_verified")},
        ),
    )


# -----------------------------------------------------------------------------
# 3. GLOBAL MEMBERSHIP BRIDGE
# -----------------------------------------------------------------------------
@admin.register(FarmMembership)
class FarmMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "farm",
        "work_commitment",
        "is_approved",
    )
    list_filter = ("farm", "is_approved", "work_commitment")
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "farm__name",
    )
    autocomplete_fields = ["user", "farm"]


# -----------------------------------------------------------------------------
# 4. WORM AUDIT LOG (LEGAL VAULT)
# -----------------------------------------------------------------------------
@admin.register(FormSignature)
class FormSignatureAdmin(admin.ModelAdmin):
    """
    A dedicated, highly-restricted vault for viewing all legal signatures globally.
    """

    list_display = (
        "user",
        "get_farm_name",
        "form",
        "digital_signature",
        "signed_at",
        "has_pdf",
    )
    list_filter = ("form__farm", "signed_at", "is_guardian_signature")
    search_fields = (
        "user__username",
        "user__email",
        "digital_signature",
        "document_hash",
        "signer_ip_address",
    )

    # Lock down ALL fields. This is an audit log, not an editable table.
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

    # Security Overrides: Prevent forging or editing signatures from the Admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
