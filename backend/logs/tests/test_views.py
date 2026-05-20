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


class LogManagementTests(TestCase):
    def setUp(self):
        self.client = Client()

        # --- Farm A (Our Farm) ---
        self.farm_a = Farm.objects.create(name="Farm A")
        self.crop_a = Crop.objects.create(farm=self.farm_a, crop_name="Tomatoes")

        self.manager_a = User.objects.create_user(
            username="mgr_a", email="mgr_a@test.com", password="p", role="farm_manager"
        )
        FarmMembership.objects.create(
            user=self.manager_a,
            farm=self.farm_a,
            is_approved=True,
            agreed_to_waiver=True,
        )

        self.vol_a = User.objects.create_user(
            username="vol_a", email="vol_a@test.com", password="p", role="volunteer"
        )
        FarmMembership.objects.create(
            user=self.vol_a, farm=self.farm_a, is_approved=True, agreed_to_waiver=True
        )

        self.log_a = LogEntry.objects.create(
            farm=self.farm_a,
            volunteer=self.vol_a,
            crop=self.crop_a,
            activity="P",
            duration_hours=5.00,
            date_logged=timezone.now().date(),
        )

        # --- Farm B (Rival Farm) ---
        self.farm_b = Farm.objects.create(name="Farm B")
        self.vol_b = User.objects.create_user(
            username="vol_b", email="vol_b@test.com", password="p", role="volunteer"
        )
        FarmMembership.objects.create(
            user=self.vol_b, farm=self.farm_b, is_approved=True, agreed_to_waiver=True
        )

        self.log_b = LogEntry.objects.create(
            farm=self.farm_b,
            volunteer=self.vol_b,
            crop=None,
            activity="O",
            duration_hours=2.00,
            date_logged=timezone.now().date(),
        )

    def test_directory_access_control(self):
        """Ensure only managers can view the master log directory."""
        self.client.force_login(self.vol_a)
        response = self.client.get(reverse("master_log_directory"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.manager_a)
        response = self.client.get(reverse("master_log_directory"))
        self.assertEqual(response.status_code, 200)

    def test_volunteer_can_edit_own_log(self):
        """Ensure volunteers can edit their own logs and route back to the dashboard."""
        self.client.force_login(self.vol_a)
        url = reverse("edit_log", args=[self.log_a.id])
        response = self.client.post(
            url,
            {
                "date_logged": timezone.now().date().strftime("%Y-%m-%d"),
                "crop": self.crop_a.id,
                "activity": "T",
                "duration_hours": 3.00,
            },
        )

        self.assertRedirects(response, reverse("log_hours"))
        self.log_a.refresh_from_db()
        self.assertEqual(self.log_a.duration_hours, 3.00)

    def test_volunteer_cannot_edit_others_log(self):
        """Ensure volunteers get a 403 Forbidden if they try to edit a peer's log."""
        vol_a2 = User.objects.create_user(
            username="vol_a2", email="vola2@test.com", password="p", role="volunteer"
        )
        FarmMembership.objects.create(
            user=vol_a2, farm=self.farm_a, is_approved=True, agreed_to_waiver=True
        )

        self.client.force_login(vol_a2)
        url = reverse("edit_log", args=[self.log_a.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_edit_any_log_in_farm(self):
        """Ensure managers can edit their volunteers' logs and route to the directory."""
        self.client.force_login(self.manager_a)
        url = reverse("edit_log", args=[self.log_a.id])
        response = self.client.post(
            url,
            {
                "date_logged": timezone.now().date().strftime("%Y-%m-%d"),
                "crop": self.crop_a.id,
                "activity": "T",
                "duration_hours": 10.00,
            },
        )

        self.assertRedirects(response, reverse("master_log_directory"))
        self.log_a.refresh_from_db()
        self.assertEqual(self.log_a.duration_hours, 10.00)

    def test_manager_cannot_edit_rival_log(self):
        """Ensure managers get a 404 Not Found if they try to edit a rival farm's log."""
        self.client.force_login(self.manager_a)
        url = reverse("edit_log", args=[self.log_b.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_volunteer_can_delete_own_log(self):
        """Ensure volunteers can delete their own logs securely."""
        self.client.force_login(self.vol_a)
        url = reverse("delete_log", args=[self.log_a.id])
        response = self.client.post(url)

        self.assertRedirects(response, reverse("log_hours"))
        self.assertFalse(LogEntry.objects.filter(id=self.log_a.id).exists())

    def test_manager_can_delete_farm_log(self):
        """Ensure managers can delete their volunteers' logs securely."""
        self.client.force_login(self.manager_a)
        url = reverse("delete_log", args=[self.log_a.id])
        response = self.client.post(url)

        self.assertRedirects(response, reverse("master_log_directory"))
        self.assertFalse(LogEntry.objects.filter(id=self.log_a.id).exists())
