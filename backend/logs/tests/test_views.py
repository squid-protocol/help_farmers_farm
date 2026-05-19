from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm, Crop
from logs.models import LogEntry
from django.utils import timezone
from accounts.models import FarmMembership

User = get_user_model()


class LogHoursIntegrationTests(TestCase):
    def setUp(self):
        # 1. Arrange: Build the world
        self.client = Client()
        self.farm = Farm.objects.create(name="Schuler Test Farm")
        self.crop = Crop.objects.create(farm=self.farm, crop_name="Heirloom Tomatoes")

        self.user = User.objects.create_user(
            username="test_volunteer",
            email="test@example.com",
            password="my_secure_password123",
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        # Force the invisible browser to log in, bypassing the security bouncer
        self.client.force_login(self.user)
        self.log_url = reverse("log_hours")

        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            crop=self.crop,
            activity="T",
            duration_hours=2.00,
            date_logged=timezone.now().date(),
        )

    def test_page_loads_for_logged_in_users(self):
        # Act: Try to visit the logging page
        response = self.client.get(self.log_url)

        # Assert: The page should load successfully (HTTP 200)
        self.assertEqual(response.status_code, 200)

    def test_successful_form_submission_creates_database_record(self):
        # Format the date as a string exactly how HTML forms send it
        today_str = timezone.now().date().strftime("%Y-%m-%d")

        response = self.client.post(
            self.log_url,
            {
                "date_logged": today_str,
                "crop": self.crop.id,
                "activity": "T",
                "duration_hours": "4.00",
            },
        )

        if response.status_code == 200:
            print("\n🚨 FORM VALIDATION FAILED. HERE IS WHY:")
            print(response.context["form"].errors)

        # Assert Part 1: Did the server accept it and redirect? (HTTP 302)
        self.assertEqual(response.status_code, 302)

        # Assert Part 2: The ultimate proof. Is it actually in the database?
        self.assertEqual(LogEntry.objects.count(), 2)  # <-- Change 1 to 2

        # Assert Part 3: Did it save the data correctly?
        saved_log = LogEntry.objects.last()  # <-- Change .first() to .last()
        self.assertEqual(saved_log.duration_hours, 4.00)
        self.assertEqual(saved_log.activity, "T")