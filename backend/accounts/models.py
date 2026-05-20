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

    legacy_years_volunteered = models.IntegerField(
        default=0, help_text="Number of years volunteered prior to using this system."
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
    # The string reference prevents circular import crashes between apps
    form = models.ForeignKey(
        "farms.ComplianceForm", on_delete=models.CASCADE, related_name="signatures"
    )

    # Legal ESIGN Requirements
    digital_signature = models.CharField(max_length=255)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents a user from signing the exact same form twice
        unique_together = ("user", "form")

    def __str__(self):
        return f"{self.user.username} signed {self.form.name}"
