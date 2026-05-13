from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # We are using AbstractUser so we keep Django's built-in auth (passwords, emails, etc.)
    # Later, we will add a ForeignKey linking the user to a specific Farm here.
    
    def __str__(self):
        return self.username