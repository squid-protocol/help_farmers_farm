import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from farms.models import Farm
from phonenumber_field.modelfields import PhoneNumberField


class CustomUser(AbstractUser):
    # Define the hierarchy of roles
    ROLE_CHOICES = [
        ("account_manager", "Account Manager (System Admin)"),
        ("farm_manager", "Farm Manager (Local Admin)"),
        ("volunteer", "Active Volunteer"),
        ("friend", "Friend (Read-Only/Legacy)"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="volunteer")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    # THE FIX: Upgraded to strict E.164 validation
    phone_number = PhoneNumberField(blank=True, null=True)

    # --- NEW: Physical Address for Legal Identity ---
    address_line1 = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Street Address"
    )
    address_line2 = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Apt/Suite/Other"
    )
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(
        max_length=2, blank=True, null=True, help_text="2-letter abbreviation"
    )
    postal_code = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="ZIP/Postal Code"
    )

    # --- NEW: Legal Verification ---
    is_email_verified = models.BooleanField(default=False)

    legacy_years_volunteered = models.IntegerField(
        default=0, help_text="Number of years volunteered prior to using this system."
    )

    # --- NEW: The Farming Persona ---
    farming_motto = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Farming Motto",
        help_text="A short blurb visible to Farm Managers about your experience or why you farm.",
    )

    # --- THE SHIMS (Tricks the app into working without rewriting all templates) ---
    @property
    def farm(self):
        """Returns the farm from their first approved membership."""
        membership = self.memberships.filter(is_approved=True).first()
        return membership.farm if membership else None

    @property
    def work_commitment(self):
        """Returns the work commitment from their first approved membership."""
        membership = self.memberships.filter(is_approved=True).first()
        return membership.work_commitment if membership else None

    # -----------------------------------------------------------------------------

    def anonymize_and_archive(self):
        """
        CCPA/GDPR compliant data scrub. Destroys the human identity
        while preserving the relational footprint for system analytics.
        """
        self.first_name = "Anonymous"
        self.last_name = "Volunteer"
        self.email = f"redacted_{uuid.uuid4().hex[:8]}@deleted.local"
        self.phone_number = None

        # Scrub the new address fields
        self.address_line1 = "Redacted per privacy request"
        self.address_line2 = None
        self.city = "Redacted"
        self.state = "XX"
        self.postal_code = "00000"

        self.username = f"archived_{uuid.uuid4().hex[:12]}"
        self.is_active = False
        self.role = "friend"  # Demote to lowest privilege
        self.avatar = None
        self.set_unusable_password()  # Cryptographically locks the account forever
        self.save()

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class FarmMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="memberships")

    # NEW: Moved work_commitment to the bridge table!
    work_commitment = models.ForeignKey(
        "farms.WorkCommitment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
    )

    custom_answers = models.JSONField(default=dict, blank=True)

    # --- NEW: Applicant Message ---
    applicant_message = models.TextField(
        blank=True,
        null=True,
        help_text="Message sent by volunteer when requesting to join.",
    )

    agreed_to_waiver = models.BooleanField(default=False)
    digital_signature = models.CharField(max_length=255, null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "farm")

    def __str__(self):
        return f"{self.user.username} - {self.farm.name} Onboarding"


class FormSignature(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signatures"
    )
    form = models.ForeignKey(
        "farms.ComplianceForm", on_delete=models.CASCADE, related_name="signatures"
    )

    digital_signature = models.CharField(max_length=255)
    signed_at = models.DateTimeField(auto_now_add=True)

    is_guardian_signature = models.BooleanField(default=False)
    guardian_relationship = models.CharField(
        max_length=100, null=True, blank=True, help_text="e.g., Parent, Legal Guardian"
    )

    # --- NEW: Immutable WORM Data ---
    signer_ip_address = models.GenericIPAddressField(null=True, blank=True)
    document_hash = models.CharField(
        max_length=64, null=True, blank=True, help_text="SHA-256 Cryptographic Hash"
    )
    pdf_receipt = models.FileField(upload_to="waivers/vault/", null=True, blank=True)
    is_vaulted = models.BooleanField(
        default=False, help_text="True if successfully synced to AWS S3 Glacier/Vault"
    )

    class Meta:
        unique_together = ("user", "form")

    def __str__(self):
        if self.is_guardian_signature:
            return f"{self.digital_signature} (Guardian) signed {self.form.name} for {self.user.username}"
        return f"{self.user.username} signed {self.form.name}"
