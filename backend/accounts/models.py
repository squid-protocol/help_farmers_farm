from django.contrib.auth.models import AbstractUser
from django.db import models
from farms.models import Farm


class CustomUser(AbstractUser):
    # Define the hierarchy of roles
    ROLE_CHOICES = [
        ("account_manager", "Account Manager (System Admin)"),
        ("farm_manager", "Farm Manager (Local Admin)"),
        ("volunteer", "Active Volunteer"),
        ("friend", "Friend (Read-Only/Legacy)"),
    ]

    # Assign the role field. Defaults to 'volunteer' when a new person signs up.
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="volunteer")

    # The existing multi-tenant link
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, null=True, blank=True, related_name="volunteers")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
