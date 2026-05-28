from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
import uuid
from phonenumber_field.modelfields import PhoneNumberField


class Farm(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    # --- NEW: Static System Identification ---
    account_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True, editable=False
    )
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # --- NEW: General Farm Info ---
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)

    # --- Season Boundaries ---
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True)

    onboarding_schema = models.JSONField(default=list, blank=True)

    # --- COMPLIANCE & LEGAL ---
    allows_joint_accounts = models.BooleanField(
        default=False,
        help_text=(
            "Bypasses strict legal waiver enforcement to allow families "
            "to share a single login. Use with caution."
        ),
    )

    # --- BILLING & SUBSCRIPTIONS ---
    TIER_CHOICES = [
        ("starter", "Starter Plan"),
        ("growth", "Growth Plan"),
        ("institutional", "Institutional Plan"),
    ]

    is_paid = models.BooleanField(default=False)
    is_comped = models.BooleanField(
        default=False, help_text="Grants lifetime free access"
    )
    subscription_tier = models.CharField(
        max_length=50, choices=TIER_CHOICES, default="starter", blank=True, null=True
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

    welcome_email_subject = models.CharField(max_length=255, default="Welcome!")
    welcome_email_body = models.TextField(default="Welcome to our farm!")

    def save(self, *args, **kwargs):
        # Auto-generate a secure, static account number if one doesn't exist
        if not self.account_number:
            self.account_number = f"FARM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def trial_days_remaining(self):
        """Calculates days left in the standard 60-day trial."""
        trial_length = 60
        days_active = (timezone.now() - self.created_at).days
        remaining = trial_length - days_active
        return max(0, remaining)

    @property
    def is_active_account(self):
        """Returns True if they paid, are comped, or are still in the 90-day trial."""
        return self.is_paid or self.is_comped or self.trial_days_remaining > 0

    @property
    def full_address(self):
        """Combines the structured fields into a single string for geocoding and display."""
        parts = [self.address_line1, self.city, self.state, self.postal_code]
        return ", ".join(filter(None, parts))

    def __str__(self):
        return self.name

    @property
    def can_use_waivers(self):
        """Feature flag for the Compliance Engine."""
        # The base $249 tier explicitly revokes liability protection
        if self.subscription_tier == "starter":
            return False
        # Free trials, Growth ($499), Institutional ($999), and comped accounts get access
        return True


class Crop(models.Model):
    # The Row-Level Multi-Tenancy link
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="crops")

    crop_name = models.CharField(max_length=100)
    category = models.CharField(max_length=100, blank=True, null=True)
    variety = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    data_source = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.crop_name} - {self.variety}" if self.variety else self.crop_name


class WorkCommitment(models.Model):
    # The list of visual choices for the manager dropdown
    SYMBOL_CHOICES = [
        ("🌑", "🌑 0% / Empty Moon"),
        ("🌒", "🌒 25% / Quarter Moon"),
        ("🌓", "🌓 50% / Half Moon"),
        ("🌔", "🌔 75% / Three-Quarter Moon"),
        ("🌕", "🌕 100% / Full Moon"),
        ("🟢", "🟢 Green Circle"),
        ("🔵", "🔵 Blue Circle"),
        ("🟣", "🟣 Purple Circle"),
        ("🟠", "🟠 Orange Circle"),
    ]

    farm = models.ForeignKey(
        Farm, on_delete=models.CASCADE, related_name="work_commitments"
    )
    name = models.CharField(max_length=100)
    required_hours = models.IntegerField(default=0)
    symbol = models.CharField(max_length=5, choices=SYMBOL_CHOICES, default="🌕")

    def __str__(self):
        return f"{self.symbol} {self.name} ({self.required_hours} hrs)"


class ComplianceForm(models.Model):
    ASSIGNMENT_CHOICES = [
        ("all", "All Volunteers"),
        ("specific", "Specific Volunteers"),
    ]

    farm = models.ForeignKey(
        Farm, on_delete=models.CASCADE, related_name="compliance_forms"
    )
    name = models.CharField(
        max_length=255, help_text="e.g., 2026 General Liability Waiver"
    )
    body_text = models.TextField()

    # --- THE TARGETING ENGINE ---
    assignment_type = models.CharField(
        max_length=10, choices=ASSIGNMENT_CHOICES, default="all"
    )
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_compliance_forms"
    )

    is_active = models.BooleanField(default=True)
    does_expire = models.BooleanField(default=False)
    expiration_date = models.DateField(null=True, blank=True)

    def is_currently_valid(self):
        if not self.is_active:
            return False
        if self.does_expire and self.expiration_date:
            if timezone.now().date() > self.expiration_date:
                return False
        return True

    def save(self, *args, **kwargs):
        if self.pk:
            orig = ComplianceForm.objects.get(pk=self.pk)
            # If the core legal text or name is changed, check for existing signatures
            if self.body_text != orig.body_text or self.name != orig.name:
                if self.signatures.exists():
                    raise ValidationError(
                        "IMMUTABILITY LOCK: You cannot alter the legal text or name of a "
                        "document that has already been signed. Please archive this form "
                        "and create a new one to preserve the audit trail."
                    )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.farm.name}"


class FarmProfile(models.Model):
    # 1. The Core Link (One-to-One ensures a farm only ever has ONE profile)
    farm = models.OneToOneField(Farm, on_delete=models.CASCADE, related_name="profile")

    # 2. Visibility & Status
    is_public = models.BooleanField(
        default=False,
        help_text="If True, your farm will appear in the public search directory.",
    )
    is_accepting_volunteers = models.BooleanField(
        default=True,
        help_text="If False, users can see your profile but the 'Request to Join' button will be hidden.",
    )

    # 3. The Pitch
    short_description = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="A quick one-sentence hook (max 150 chars).",
    )
    about_us = models.TextField(
        blank=True, null=True, help_text="Rich text HTML generated by the Trix editor."
    )

    volunteer_perks = models.TextField(
        blank=True,
        null=True,
        help_text="e.g., Free produce, college credit, community meals.",
    )
    physical_requirements = models.TextField(
        blank=True,
        null=True,
        help_text="e.g., Must lift 50lbs, kneeling required, 18+ only.",
    )

    # 4. Search Tags (Stored safely as a JSON array)
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of strings e.g., ['USDA Organic', 'No-Till', 'Pesticide-Free']",
    )

    # 5. Media & Branding
    logo = models.ImageField(upload_to="farm_media/logos/", blank=True, null=True)
    cover_photo = models.ImageField(
        upload_to="farm_media/covers/", blank=True, null=True
    )

    # 6. Social Links
    website_url = models.URLField(blank=True, null=True)
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"Public Profile: {self.farm.name}"


class FarmImage(models.Model):
    """Handles the Action Shot Gallery for public profiles."""

    profile = models.ForeignKey(
        FarmProfile, on_delete=models.CASCADE, related_name="gallery_images"
    )
    image = models.ImageField(upload_to="farm_media/gallery/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gallery Image for {self.profile.farm.name}"
