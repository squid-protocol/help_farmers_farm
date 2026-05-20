from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid


class Farm(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- NEW: Static System Identification ---
    account_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True, editable=False
    )

    # --- NEW: General Farm Info ---
    address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)

    # --- Season Boundaries ---
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True)

    onboarding_schema = models.JSONField(default=list, blank=True)

    # --- BILLING & SUBSCRIPTIONS ---
    is_paid = models.BooleanField(default=False)
    is_comped = models.BooleanField(
        default=False, help_text="Grants lifetime free access"
    )
    subscription_tier = models.CharField(max_length=50, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

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

    def __str__(self):
        return self.name


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

    def __str__(self):
        return f"{self.name} - {self.farm.name}"
