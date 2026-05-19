from django.db import models
from django.utils import timezone
from datetime import timedelta

class Farm(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Season Boundaries ---
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True)

    # --- Custom Onboarding Data ---
    liability_waiver_text = models.TextField(blank=True, null=True)
    onboarding_schema = models.JSONField(default=list, blank=True)

# --- BILLING & SUBSCRIPTIONS ---
    is_paid = models.BooleanField(default=False)
    subscription_tier = models.CharField(max_length=50, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

    # --- TRIAL LOGIC ---
    @property
    def trial_days_remaining(self):
        """Calculates days left in the 60-day trial."""
        expiration_date = self.created_at + timedelta(days=60)
        remaining = (expiration_date - timezone.now()).days
        return max(0, remaining)

    @property
    def is_active_account(self):
        """Returns True if they paid OR if they are still in the 60-day trial."""
        return self.is_paid or self.trial_days_remaining > 0

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