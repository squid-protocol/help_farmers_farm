from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from farms.models import Farm, Crop
from django.contrib.auth import get_user_model
from logs.models import LogEntry

User = get_user_model()


class LogEntryModelTests(TestCase):
    def setUp(self):
        # 1. Set up the baseline "controlled environment"
        self.farm = Farm.objects.create(name="Test Farm")
        self.user = User.objects.create_user(
            username="testvol", password="password", farm=self.farm
        )
        self.crop = Crop.objects.create(farm=self.farm, crop_name="Test Tomatoes")

    def test_future_date_rejected(self):
        # 2. The Hypothesis: Logging hours for tomorrow should fail.
        tomorrow = timezone.now().date() + timedelta(days=1)

        future_log = LogEntry(
            farm=self.farm,
            volunteer=self.user,
            crop=self.crop,
            activity="P",
            duration_hours=2.00,
            date_logged=tomorrow,
        )

        # 3. The Experiment: We assert that calling full_clean() raises a ValidationError
        with self.assertRaises(ValidationError):
            future_log.full_clean()
