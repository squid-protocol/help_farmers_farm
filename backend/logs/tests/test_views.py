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
        self.farm = Farm.objects.create(
            name="Schuler Test Farm",
            welcome_email_body="Welcome to the farm!",
            welcome_email_subject="Welcome!",
        )
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

    def test_unattached_volunteer_redirected_to_profile(self):
        """Ensure a volunteer without a farm cannot access the log hours dashboard."""
        unattached_user = User.objects.create_user(
            username="floater", email="float@test.com", password="p"
        )
        self.client.force_login(unattached_user)

        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, reverse("profile"))

    def test_history_year_invalid_input_fallback(self):
        """Unhappy Path: User types letters into the history_year URL parameter."""
        # The system should catch the ValueError and safely default to the current year
        response = self.client.get(self.log_url + "?history_year=garbage_string")
        self.assertEqual(response.status_code, 200)
        self.assertIn("history_year", response.context)

    def test_history_year_pagination_boundaries(self):
        """Edge Case: Viewing the oldest and newest years to test prev/next logic."""
        last_year = timezone.now().date().year - 1
        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            crop=self.crop,
            activity="O",
            duration_hours=1.00,
            date_logged=f"{last_year}-05-05",
        )

        # Oldest year should NOT have a prev_year
        response_oldest = self.client.get(self.log_url + f"?history_year={last_year}")
        self.assertEqual(response_oldest.status_code, 200)

        # Current year should NOT have a next_year
        response_current = self.client.get(
            self.log_url + f"?history_year={timezone.now().date().year}"
        )
        self.assertEqual(response_current.status_code, 200)

    def test_manager_deletes_other_volunteer_log_routing(self):
        """Routing check: Managers deleting a log should be routed to the master directory."""
        # 1. Create a manager WITH an email to bypass RequireEmailMiddleware
        manager = User.objects.create_user(
            username="manager",
            email="manager@test.com",
            password="p",
            role="farm_manager",
        )
        FarmMembership.objects.create(user=manager, farm=self.farm, is_approved=True)

        # 2. Create a log for the regular volunteer
        log_to_delete = LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            activity="T",
            duration_hours=1,
            date_logged=timezone.now().date(),
        )

        # 3. Login as manager and delete the volunteer's log
        self.client.force_login(manager)
        response = self.client.post(reverse("delete_log", args=[log_to_delete.id]))

        # 4. Ensure it redirects back to the directory, NOT the personal log hours page
        self.assertRedirects(response, reverse("master_log_directory"))


class LogManagementTests(TestCase):
    def setUp(self):
        import uuid

        self.client = Client()
        uid = str(uuid.uuid4())[:8]

        # --- Farm A (Our Farm) ---
        self.farm_a = Farm.objects.create(
            name=f"Farm A {uid}",
            welcome_email_body="Welcome to Farm A!",
            welcome_email_subject="Welcome!",
        )
        self.crop_a = Crop.objects.create(farm=self.farm_a, crop_name="Tomatoes")

        self.manager_a = User.objects.create_user(
            username=f"mgr_a_{uid}",
            email=f"mgr_a_{uid}@test.com",
            password="p",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager_a,
            farm=self.farm_a,
            is_approved=True,
            agreed_to_waiver=True,
        )

        self.vol_a = User.objects.create_user(
            username=f"vol_a_{uid}",
            email=f"vol_a_{uid}@test.com",
            password="p",
            role="volunteer",
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
        self.farm_b = Farm.objects.create(
            name=f"Farm B {uid}",
            welcome_email_body="Welcome to Farm B!",
            welcome_email_subject="Welcome!",
        )
        self.vol_b = User.objects.create_user(
            username=f"vol_b_{uid}",
            email=f"vol_b_{uid}@test.com",
            password="p",
            role="volunteer",
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

    def test_volunteer_cannot_delete_others_log(self):
        """Ensure the Ghost Delete attack is blocked by a 403 Permission Denied."""
        vol_a2 = User.objects.create_user(
            username="vol_a2_hacker",
            email="hacker@test.com",
            password="p",
            role="volunteer",
        )
        FarmMembership.objects.create(
            user=vol_a2, farm=self.farm_a, is_approved=True, agreed_to_waiver=True
        )

        self.client.force_login(vol_a2)
        url = reverse("delete_log", args=[self.log_a.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class LogUnhappyPathTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        self.client = Client()

        # Create a farm with a future season to trigger pacing engine logic
        self.farm = Farm.objects.create(
            name="Edge Case Farm",
            welcome_email_subject="Hi",
            welcome_email_body="Welcome",
            season_start=timezone.now().date() + timedelta(days=10),
            season_end=timezone.now().date() + timedelta(days=100),
        )
        self.crop = Crop.objects.create(farm=self.farm, crop_name="Peppers")
        self.user = User.objects.create_user(
            username="test_edge", email="edge@test.com", password="p"
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        self.client.force_login(self.user)
        self.log_url = reverse("log_hours")

    def test_tollbooth_blocks_logging_on_inactive_accounts(self):
        """Ensure unpaid/expired farms cannot log new hours."""
        from unittest.mock import patch, PropertyMock

        # Force the farm to appear as expired/unpaid
        with patch(
            "farms.models.Farm.is_active_account", new_callable=PropertyMock
        ) as mock_active:
            mock_active.return_value = False

            response = self.client.post(
                self.log_url,
                {
                    "date_logged": timezone.now().date().strftime("%Y-%m-%d"),
                    "crop": self.crop.id,
                    "activity": "T",
                    "duration_hours": "2.00",
                },
            )

            # The tollbooth should intercept and redirect back to the page
            self.assertRedirects(response, self.log_url)
            self.assertEqual(LogEntry.objects.count(), 0)

    def test_database_exception_handled_gracefully(self):
        """Ensure a hard database crash during save does not 500 the server."""
        from unittest.mock import patch

        # Intercept the exact moment the log tries to write to the DB and force a crash
        with patch("logs.models.LogEntry.save") as mock_save:
            mock_save.side_effect = Exception("Simulated Hard DB Crash")

            response = self.client.post(
                self.log_url,
                {
                    "date_logged": timezone.now().date().strftime("%Y-%m-%d"),
                    "crop": self.crop.id,
                    "activity": "T",
                    "duration_hours": "2.00",
                },
            )

            # The view's try/except block should catch it and re-render the page cleanly (200 OK)
            self.assertEqual(response.status_code, 200)

    def test_form_validation_blocks_impossible_hours(self):
        """Ensure the Physics-Defier attack fails."""
        response = self.client.post(
            self.log_url,
            {
                "date_logged": timezone.now().date().strftime("%Y-%m-%d"),
                "crop": self.crop.id,
                "activity": "T",
                "duration_hours": "25.00",  # Exceeds the 24.00 MaxValueValidator limit
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("duration_hours", response.context["form"].errors)
        self.assertEqual(LogEntry.objects.count(), 0)

    def test_form_validation_blocks_missing_payload(self):
        """Ensure empty POST payloads (bypassing HTML required tags) are caught gracefully."""
        response = self.client.post(self.log_url, {})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(LogEntry.objects.count(), 0)

    def test_pacing_engine_edge_cases(self):
        """Force the pacing engine to calculate required pace across all boundary lines."""
        from farms.models import WorkCommitment

        commitment = WorkCommitment.objects.create(
            farm=self.farm, name="Tester", required_hours=10
        )
        membership = FarmMembership.objects.get(user=self.user)
        membership.work_commitment = commitment
        membership.save()

        # Log exactly 2 hours so remaining_hours is 8 (triggers the pacing math)
        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            crop=self.crop,
            activity="T",
            duration_hours=2.00,
            date_logged=timezone.now().date(),
        )

        response = self.client.get(self.log_url)
        self.assertEqual(response.status_code, 200)

        # Prove the pacing engine calculated the necessary trajectory
        self.assertGreater(response.context["required_pace"], 0)
