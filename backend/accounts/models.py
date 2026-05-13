from django.contrib.auth.models import AbstractUser
from django.db import models
from farms.models import Farm

class CustomUser(AbstractUser):
    # Link the user to a farm. 
    # null=True, blank=True ensures you can create a master admin account that doesn't belong to just one farm.
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, null=True, blank=True, related_name='volunteers')
    
    def __str__(self):
        return self.username