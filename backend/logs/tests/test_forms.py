from django.test import TestCase
from logs.forms import LogEntryForm
from farms.models import Farm, Crop
from django.utils import timezone
from datetime import timedelta


class LogEntryFormTests(TestCase):
    def setUp(self):
        # Create the required database objects to populate the form
        self.farm = Farm.objects.create(name="Schuler Test Farm")
        self.crop = Crop.objects.create(farm=self.farm, crop_name="Heirloom Tomatoes")

    def test_form_rejects_negative_hours(self):
        # Act: Fill out the form with -5 hours
        form_data = {
            "date_logged": timezone.now().date(),
            "crop": self.crop.id,
            "activity": "T",
            "duration_hours": -5.00,  # THE BAD DATA
        }
        form = LogEntryForm(data=form_data)

        # Assert: The form MUST be invalid
        self.assertFalse(form.is_valid())
        self.assertIn("duration_hours", form.errors)

    def test_form_rejects_future_dates(self):
        # Act: Fill out the form with tomorrow's date
        tomorrow = timezone.now().date() + timedelta(days=1)
        form_data = {
            "date_logged": tomorrow,  # THE BAD DATA
            "crop": self.crop.id,
            "activity": "T",
            "duration_hours": 2.00,
        }
        form = LogEntryForm(data=form_data)

        # Assert: The form MUST be invalid
        self.assertFalse(form.is_valid())
        self.assertIn("date_logged", form.errors)
