from django.db import models


class Farm(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

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
