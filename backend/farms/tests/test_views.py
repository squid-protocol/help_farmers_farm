from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm, Crop, WorkCommitment, ComplianceForm
from accounts.models import FarmMembership
from unittest.mock import patch

User = get_user_model()


class SecurityIDORTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Build Farm A (The Good Guys)
        self.farm_a = Farm.objects.create(name="Schuler Test Farm")

        self.manager_a = User.objects.create_user(
            username="manager_a",
            email="manager_a@example.com",
            password="secure",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager_a, farm=self.farm_a, is_approved=True
        )

        self.volunteer_a = User.objects.create_user(
            username="vol_a",
            email="vol_a@example.com",
            password="secure",
        )
        FarmMembership.objects.create(
            user=self.volunteer_a, farm=self.farm_a, is_approved=True
        )

        # 2. Build Farm B (The Rivals)
        self.farm_b = Farm.objects.create(name="Rival Valley Farms")
        self.volunteer_b = User.objects.create_user(
            username="vol_b",
            email="vol_b@example.com",
            password="secure",
        )
        FarmMembership.objects.create(
            user=self.volunteer_b, farm=self.farm_b, is_approved=True
        )

        # 3. Build a System Admin (Staff)
        self.staff_user = User.objects.create_user(
            username="staff_admin",
            email="staff@example.com",
            password="secure",
            is_staff=True,
        )
        FarmMembership.objects.create(
            user=self.staff_user, farm=self.farm_a, is_approved=True
        )

    def test_manager_can_view_own_volunteer(self):
        self.client.force_login(self.manager_a)
        url = reverse("volunteer_detail", args=[self.volunteer_a.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_view_rival_volunteer_idor(self):
        self.client.force_login(self.manager_a)
        url = reverse("volunteer_detail", args=[self.volunteer_b.id])
        response = self.client.get(url)

        # Expect a 403 Forbidden instead of a 404 Not Found
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_any_volunteer(self):
        """Ensure staff users can bypass the farm isolation boundary."""
        self.client.force_login(self.staff_user)
        url = reverse("volunteer_detail", args=[self.volunteer_b.id])
        response = self.client.get(url)

        # Staff should be allowed to view the rival volunteer
        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_toggle_rival_volunteer(self):
        self.client.force_login(self.manager_a)
        url = reverse("toggle_user_status", args=[self.volunteer_b.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        # Ensure the rival volunteer is still active
        self.volunteer_b.refresh_from_db()
        self.assertTrue(self.volunteer_b.is_active)

    def test_manager_cannot_toggle_another_manager(self):
        manager_a2 = User.objects.create_user(
            username="manager_a2",
            email="manager_a2@example.com",
            password="secure",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=manager_a2, farm=self.farm_a, is_approved=True
        )

        self.client.force_login(self.manager_a)
        url = reverse("toggle_user_status", args=[manager_a2.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        # Ensure the manager is still active
        manager_a2.refresh_from_db()
        self.assertTrue(manager_a2.is_active)

    def test_manager_cannot_deactivate_self(self):
        """Ensure a manager cannot accidentally archive their own account."""
        self.client.force_login(self.manager_a)
        url = reverse("toggle_user_status", args=[self.manager_a.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_toggle_own_volunteer(self):
        self.client.force_login(self.manager_a)
        url = reverse("toggle_user_status", args=[self.volunteer_a.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # Ensure the volunteer was successfully soft-deleted (archived)
        self.volunteer_a.refresh_from_db()
        self.assertFalse(self.volunteer_a.is_active)

    def test_manager_dashboard_loads_successfully(self):
        self.client.force_login(self.manager_a)
        url = reverse("manager_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "farms/manager_dashboard.html")


class ManagerDashboardActionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Action Test Farm", subscription_tier="starter"
        )

        # Create a manager with an email so they pass the Email Tollbooth
        self.manager = User.objects.create_user(
            username="action_manager",
            email="manager@test.com",
            password="securepassword",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager,
            farm=self.farm,
            is_approved=True,
            agreed_to_waiver=True,  # Pass the Waiver Tollbooth
        )

        self.dashboard_url = reverse("manager_dashboard")

    def test_manager_can_create_crop(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            self.dashboard_url,
            {
                "submit_crop": "true",
                "crop_name": "Ghost Peppers",
                "variety": "Spicy",
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Crop.objects.filter(farm=self.farm, crop_name="Ghost Peppers").exists()
        )

    def test_manager_can_create_volunteer(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            self.dashboard_url,
            {
                "submit_volunteer": "true",
                "username": "new_guy",
                "first_name": "New",
                "last_name": "Guy",
                "email": "newguy@example.com",
                "phone_number": "555-1234",
                "legacy_years_volunteered": 0,
                "role": "volunteer",
                "password": "temporarypassword123",
            },
        )

        self.assertEqual(response.status_code, 302)

        # Verify the user was created
        new_user = User.objects.filter(username="new_guy").first()
        self.assertIsNotNone(new_user)

        # CRITICAL: Verify the bridge table was created linking them to the farm!
        self.assertTrue(
            FarmMembership.objects.filter(user=new_user, farm=self.farm).exists()
        )

    @patch("django.db.models.query.QuerySet.count")
    def test_manager_capacity_limit_blocks_creation_starter(self, mock_count):
        """Ensure the tollbooth stops creation when Starter limit (50) is reached."""
        self.client.force_login(self.manager)
        mock_count.return_value = 50

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_volunteer": "true",
                "username": "too_many_guys",
                "email": "overflow@example.com",
                "role": "volunteer",
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="too_many_guys").exists())

    @patch("django.db.models.query.QuerySet.count")
    def test_manager_capacity_limit_blocks_creation_growth(self, mock_count):
        """Ensure the tollbooth stops creation when Growth limit (200) is reached."""
        self.farm.subscription_tier = "growth"
        self.farm.save()
        self.client.force_login(self.manager)
        mock_count.return_value = 200

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_volunteer": "true",
                "username": "growth_overflow",
                "email": "growth_overflow@example.com",
                "role": "volunteer",
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username="growth_overflow").exists())

    def test_manager_can_create_commitment(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_commitment": "true",
                "name": "Quarter Share",
                "required_hours": 20,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            WorkCommitment.objects.filter(farm=self.farm, name="Quarter Share").exists()
        )

    def test_manager_can_create_compliance_form(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_compliance_form": "true",
                "name": "2026 Tractor Safety",
                "body_text": "Keep your hands inside the vehicle.",
                "assignment_type": "all",
                "is_active": True,
                "does_expire": False,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ComplianceForm.objects.filter(
                farm=self.farm, name="2026 Tractor Safety"
            ).exists()
        )

    def test_manager_can_update_farm_settings(self):
        """Ensure settings save, and phone numbers are normalized."""
        self.client.force_login(self.manager)

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_farm_settings": "true",
                "name": "Updated Farm Name",
                "phone_number": "(201) 555-0123",  # A structurally valid US number
                "season_start": "2026-05-01",
                "season_end": "2026-10-31",
            },
        )

        # The form should succeed and redirect (302)
        self.assertEqual(response.status_code, 302)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, "Updated Farm Name")
        # Prove the library converted it to the standard E.164 format!
        self.assertEqual(str(self.farm.phone_number), "+12015550123")

    def test_manager_cannot_save_invalid_phone_number(self):
        """Ensure the form rejects garbage data in the phone field."""
        self.client.force_login(self.manager)

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_farm_settings": "true",
                "name": "Updated Farm Name",
                "phone_number": "Call me later!",  # Complete garbage
            },
        )

        # The form should fail validation and re-render the page (HTTP 200), NOT redirect (HTTP 302)
        self.assertEqual(response.status_code, 200)
        # Bulletproof check: Ask the form itself if it rejected the phone number
        self.assertIn("phone_number", response.context["farm_form"].errors)

    def test_farm_manager_role_choices_are_restricted(self):
        """Ensure Farm Managers cannot elevate privileges to admin levels."""
        from farms.forms import VolunteerCreationForm, VolunteerEditForm

        # Instantiate the creation form as the Farm Manager
        create_form = VolunteerCreationForm(request_user=self.manager)
        create_roles = [choice[0] for choice in create_form.fields["role"].choices]

        # Verify the high-level roles were stripped out
        self.assertNotIn("account_manager", create_roles)
        self.assertNotIn("farm_manager", create_roles)
        self.assertIn("volunteer", create_roles)

        # Verify the exact same protection applies to the Edit form
        edit_form = VolunteerEditForm(request_user=self.manager)
        edit_roles = [choice[0] for choice in edit_form.fields["role"].choices]

        self.assertNotIn("account_manager", edit_roles)
        self.assertNotIn("farm_manager", edit_roles)


class FarmEditAndToggleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Edit Test Farm")
        self.rival_farm = Farm.objects.create(name="Rival Edit Farm")

        self.manager = User.objects.create_user(
            username="editor_manager",
            email="edit@test.com",
            password="pass",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager, farm=self.farm, is_approved=True
        )
        self.client.force_login(self.manager)

        self.manager_2 = User.objects.create_user(
            username="other_manager",
            email="edit2@test.com",
            password="pass",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager_2, farm=self.farm, is_approved=True
        )

        self.volunteer = User.objects.create_user(
            username="vol", password="p", role="volunteer"
        )
        FarmMembership.objects.create(
            user=self.volunteer, farm=self.farm, is_approved=True
        )

        self.rival_volunteer = User.objects.create_user(
            username="rival_vol", password="p", role="volunteer"
        )
        FarmMembership.objects.create(
            user=self.rival_volunteer, farm=self.rival_farm, is_approved=True
        )

        self.crop = Crop.objects.create(farm=self.farm, crop_name="Old Tomatoes")
        self.commitment = WorkCommitment.objects.create(
            farm=self.farm, name="Old Share", required_hours=10
        )

    def test_edit_crop_get_and_post(self):
        url = reverse("edit_crop", args=[self.crop.id])

        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test POST
        response = self.client.post(
            url, {"crop_name": "New Tomatoes", "is_active": True}
        )
        self.assertRedirects(response, reverse("manager_dashboard"))
        self.crop.refresh_from_db()
        self.assertEqual(self.crop.crop_name, "New Tomatoes")

    def test_toggle_crop_status(self):
        url = reverse("toggle_crop_status", args=[self.crop.id])
        response = self.client.post(url)

        self.assertRedirects(response, reverse("manager_dashboard"))
        self.crop.refresh_from_db()
        self.assertFalse(self.crop.is_active)

    def test_edit_volunteer_get_and_post(self):
        url = reverse("edit_volunteer", args=[self.volunteer.id])

        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test POST
        response = self.client.post(
            url, {"username": "updated_vol", "role": "volunteer", "is_active": True}
        )
        self.assertRedirects(response, reverse("manager_dashboard"))
        self.volunteer.refresh_from_db()
        self.assertEqual(self.volunteer.username, "updated_vol")

    def test_edit_volunteer_idor_cannot_edit_rival(self):
        """Ensure a manager cannot edit a volunteer in a different farm."""
        url = reverse("edit_volunteer", args=[self.rival_volunteer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_edit_volunteer_idor_cannot_edit_other_manager(self):
        """Ensure a farm manager cannot edit another farm manager's profile."""
        url = reverse("edit_volunteer", args=[self.manager_2.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_edit_commitment_get_and_post(self):
        url = reverse("edit_commitment", args=[self.commitment.id])

        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test POST
        response = self.client.post(url, {"name": "New Share", "required_hours": 30})
        self.assertRedirects(response, reverse("manager_dashboard"))
        self.commitment.refresh_from_db()
        self.assertEqual(self.commitment.required_hours, 30)


class FarmReportingViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Report Farm", season_start="2026-01-01", season_end="2026-12-31"
        )

        self.manager = User.objects.create_user(
            username="report_manager",
            email="report@test.com",
            password="pass",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager, farm=self.farm, is_approved=True
        )
        self.client.force_login(self.manager)

    def test_farm_impact_view(self):
        url = reverse("farm_impact")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "farms/farm_impact.html")

    def test_progress_report_view(self):
        url = reverse("progress_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "farms/progress_report.html")

    def test_progress_report_invalid_year_fallback(self):
        """Covers line 252-253: ValueError when passing a string instead of a year."""
        url = reverse("progress_report")
        response = self.client.get(url, {"year": "not_a_number"})
        self.assertEqual(response.status_code, 200)

    def test_progress_report_future_year(self):
        """Covers line 258: Skipping the current-year pacing logic for a future year."""
        url = reverse("progress_report")
        response = self.client.get(url, {"year": "2099"})
        self.assertEqual(response.status_code, 200)


class WorkspaceSwitchTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.farm1 = Farm.objects.create(name="Farm 1")
        self.farm2 = Farm.objects.create(name="Farm 2")

        self.user = User.objects.create_user(
            username="dual_agent", email="agent@test.com", password="p"
        )
        # Approve user in both farms
        FarmMembership.objects.create(user=self.user, farm=self.farm1, is_approved=True)
        FarmMembership.objects.create(user=self.user, farm=self.farm2, is_approved=True)

        self.client.force_login(self.user)

    def test_switch_active_farm(self):
        url = reverse("switch_active_farm")

        # Switch to farm 2
        response = self.client.post(
            url, {"farm_id": str(self.farm2.id), "next": "/log-hours/"}
        )

        self.assertRedirects(response, "/log-hours/")
        self.assertEqual(self.client.session["active_farm_id"], self.farm2.id)

    def test_switch_active_farm_no_next_url(self):
        """Ensure it falls back to a safe default if no 'next' URL is provided."""
        url = reverse("switch_active_farm")

        response = self.client.post(
            url,
            {
                "farm_id": str(self.farm2.id)
                # Purposely omitting "next"
            },
        )

        self.assertRedirects(response, "/log-hours/")
        self.assertEqual(self.client.session["active_farm_id"], self.farm2.id)
