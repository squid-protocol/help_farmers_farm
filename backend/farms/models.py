from django.db import models


class Farm(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- NEW: Season Boundaries ---
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True)

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
    name = models.CharField(max_length=100)  # e.g., "Full Share", "Half Share"
    required_hours = models.IntegerField(default=0)  # e.g., 80, 50

    # NEW FIELD
    symbol = models.CharField(max_length=5, choices=SYMBOL_CHOICES, default="🌕")

    def __str__(self):
        return f"{self.symbol} {self.name} ({self.required_hours} hrs)"
