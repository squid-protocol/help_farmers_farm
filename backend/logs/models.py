from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from farms.models import Farm, Crop


# PROTECTION 1: The "Time Machine" Blocker
def validate_not_in_future(value):
    if value > timezone.now().date():
        raise ValidationError("You cannot log hours for a future date.")


class LogEntry(models.Model):
    ACTIVITY_CHOICES = [
        ("P", "Planting"),
        ("T", "Tending"),
        ("H", "Harvesting"),
        ("C", "Cultivating (Weeding)"),
        ("O", "Off Season Work"),
        ("M", "Move Dirt"),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="logs")

    # PROTECTION 2: Prevent the "Nuclear Option"
    # Using SET_NULL instead of CASCADE means if a manager deletes a Volunteer or a Crop,
    # the historical hours don't magically disappear from the Farm's total analytics.
    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="logs",
    )
    crop = models.ForeignKey(
        Crop, on_delete=models.SET_NULL, null=True, related_name="logs"
    )

    activity = models.CharField(max_length=1, choices=ACTIVITY_CHOICES)

    # Using DecimalField is safer for exact math (like hours/money) than FloatField
    duration_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[
            MinValueValidator(0.01, message="Hours must be greater than 0."),
            MaxValueValidator(
                24.00, message="You cannot log more than 24 hours in a single entry."
            ),
        ],
    )

    # NEW: Qualitative Shift Notes
    notes = models.TextField(max_length=2000, blank=True, null=True)

    # Attached the time-machine blocker here
    date_logged = models.DateField(validators=[validate_not_in_future])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # PROTECTION 3: The "Double-Click" Blocker
        # If a user clicks 'Submit' twice really fast, the database will reject the second exact duplicate.
        unique_together = [
            "volunteer",
            "crop",
            "activity",
            "date_logged",
            "duration_hours",
        ]

    def __str__(self):
        # Added quick checks in case volunteer or crop was deleted (SET_NULL)
        vol_name = self.volunteer.username if self.volunteer else "Deleted User"
        crop_name = self.crop.crop_name if self.crop else "Deleted Crop"
        return f"{vol_name} - {self.get_activity_display()} {crop_name} - {self.duration_hours}h"
