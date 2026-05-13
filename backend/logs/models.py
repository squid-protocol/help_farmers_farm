from django.db import models
from django.conf import settings
from farms.models import Farm, Crop

class LogEntry(models.Model):
    ACTIVITY_CHOICES = [
        ('P', 'Plant'),
        ('T', 'Tend'),
        ('H', 'Harvest'),
        ('O', 'Off-Season/Other')
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='logs')
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='logs')
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='logs')
    activity = models.CharField(max_length=1, choices=ACTIVITY_CHOICES)
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2)
    date_logged = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.volunteer} - {self.get_activity_display()} {self.crop} - {self.duration_hours}h"