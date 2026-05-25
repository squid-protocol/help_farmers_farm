from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm, Crop, WorkCommitment, ComplianceForm, FarmProfile
from accounts.models import FarmMembership
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from logs.models import LogEntry
from farms.models import FarmImage

User = get_user_model()

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
            reverse("volunteer_roster"),
            {
                "submit_volunteer": "true",
                "username": "new_guy",
                "first_name": "New",
                "last_name": "Guy",
                "email": "newguy@example.com",
                "phone_number": "(201) 555-0123",
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
            reverse("volunteer_roster"),
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
            reverse("volunteer_roster"),
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

    def test_manager_cannot_create_compliance_form_on_starter_tier(self):
        """Ensure the UI blocks compliance form creation for Starter tiers."""
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
        # Verify the database physically rejected the form creation
        self.assertFalse(
            ComplianceForm.objects.filter(
                farm=self.farm, name="2026 Tractor Safety"
            ).exists()
        )

    def test_manager_can_create_compliance_form_on_growth_tier(self):
        """Ensure the form creation works if they upgrade to the Growth tier."""
        self.farm.subscription_tier = "growth"
        self.farm.save()
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

    def test_manager_can_update_public_profile(self):
        """Ensure managers can successfully update their marketing profile and tags."""
        self.client.force_login(self.manager)

        # Simulating Tagify's JSON payload
        tagify_json = '[{"value":"USDA Organic"},{"value":"No-Till"}]'

        # THE FIX: Point to the correct view URL
        response = self.client.post(
            reverse("edit_farm_profile"),
            {
                "submit_profile": "true",
                "is_public": True,
                "short_description": "We grow the best carrots.",
                "about_us": "<div>Rich text content</div>",
                "tags": tagify_json,
                "website_url": "https://schulerfarms.com",
                "volunteer_perks": "Free vegetables.",
                "physical_requirements": "Ability to lift 30 lbs.",
            },
        )

        self.assertEqual(response.status_code, 302)

        # Verify it actually saved to the database correctly
        profile = self.farm.profile
        self.assertTrue(profile.is_public)
        self.assertFalse(profile.is_accepting_volunteers)
        self.assertEqual(profile.short_description, "We grow the best carrots.")
        self.assertEqual(profile.website_url, "https://schulerfarms.com")

        # Verify the custom clean_tags method properly parsed the JSON array
        self.assertIn("USDA Organic", profile.tags)
        self.assertIn("No-Till", profile.tags)

    def test_manager_can_update_farm_settings(self):
        """Ensure settings save, and phone numbers are normalized."""
        self.client.force_login(self.manager)

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_farm_settings": "true",
                "name": "Updated Farm Name",
                "phone_number": "(201) 555-0123",  # A structurally valid US number
                "welcome_email_subject": "Welcome to the farm!",
                "welcome_email_body": "We are glad to have you.",
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

    def test_manager_can_update_profile_tags_without_javascript(self):
        """STABILITY: Ensure the backend gracefully falls back to comma-separated strings if Tagify JS fails."""
        self.client.force_login(self.manager)

        # THE FIX: Point to the correct view URL
        response = self.client.post(
            reverse("edit_farm_profile"),
            {
                "submit_profile": "true",
                "is_public": True,
                "tags": "Heirloom, Hand-Picked, Pesticide Free",
                "short_description": "We grow the best carrots.",
                "about_us": "<div>Rich text content</div>",
                "website_url": "https://schulerfarms.com",
                "volunteer_perks": "Free vegetables.",
                "physical_requirements": "Ability to lift 30 lbs.",
            },
        )

        self.assertEqual(response.status_code, 302)

        # --- BULLETPROOF DEBUG BLOCK ---
        if response.status_code == 200:
            print("\n" + "=" * 50)
            print("🚨 FORM VALIDATION FAILED! 🚨")
            # response.context is a list of dictionaries in Django tests
            for context_dict in response.context:
                if isinstance(context_dict, dict):
                    for key, val in context_dict.items():
                        if hasattr(val, "errors") and val.errors:
                            print(f"Errors in form '{key}': {val.errors}")
            print("=" * 50 + "\n")
        # -------------------------------

        self.assertEqual(response.status_code, 302)

        # Verify the custom clean_tags method caught the ValueError and split it by commas
        self.farm.profile.refresh_from_db()
        self.assertIn("Heirloom", self.farm.profile.tags)
        self.assertIn("Hand-Picked", self.farm.profile.tags)
        self.assertIn("Pesticide Free", self.farm.profile.tags)


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
        self.assertRedirects(response, reverse("volunteer_roster"))
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

    def test_compliance_audit_view(self):
        """Phase 4: Ensure the manager can view the signature audit trail."""
        from farms.models import ComplianceForm
        from accounts.models import FormSignature

        form = ComplianceForm.objects.create(
            farm=self.farm, name="Audit Test Form", body_text="text"
        )
        FormSignature.objects.create(
            user=self.manager, form=form, digital_signature="Report Manager"
        )

        url = reverse("compliance_audit", args=[form.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "farms/compliance_audit.html")
        self.assertIn("signatures", response.context)
        self.assertEqual(response.context["signatures"].count(), 1)

    def test_compliance_audit_idor_protection(self):
        """Phase 4: Ensure a manager cannot view another farm's audit trail."""
        from farms.models import ComplianceForm

        other_farm = Farm.objects.create(name="Other Farm")
        other_form = ComplianceForm.objects.create(
            farm=other_farm, name="Other Form", body_text="text"
        )

        url = reverse("compliance_audit", args=[other_form.id])
        response = self.client.get(url)

        # Should return 404 because get_object_or_404 enforces farm=request.active_farm
        self.assertEqual(response.status_code, 404)


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


class FarmUnhappyPathTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Secure Farm", subscription_tier="growth")
        self.rival_farm = Farm.objects.create(name="Rival Farm")

        self.manager = User.objects.create_user(
            username="secure_manager",
            email="sec@test.com",
            password="p",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager, farm=self.farm, is_approved=True
        )

        self.client.force_login(self.manager)
        self.dashboard_url = reverse("manager_dashboard")

    def test_workspace_hijacking_blocked(self):
        """Ensure a user cannot switch their active session to a farm they do not belong to."""
        url = reverse("switch_active_farm")

        # Prime the session with the authorized farm
        session = self.client.session
        session["active_farm_id"] = self.farm.id
        session.save()

        # Attempt to hijack the session by injecting the Rival Farm ID
        response = self.client.post(
            url, {"farm_id": str(self.rival_farm.id), "next": "/log-hours/"}
        )

        self.assertRedirects(response, "/log-hours/")

        # The session ID MUST remain the original farm, blocking the hijack
        self.assertEqual(self.client.session["active_farm_id"], self.farm.id)

    def test_manager_dashboard_broadcast_and_welcome_execution(self):
        """Ensure the Comms panel successfully processes broadcasts and welcome template updates."""
        from unittest.mock import patch

        # 1. Update Welcome Template
        response1 = self.client.post(
            self.dashboard_url,
            {
                "submit_welcome_email": "true",
                "welcome_email_subject": "New Subject!",
                "welcome_email_body": "New Body!",
            },
        )
        self.assertRedirects(response1, self.dashboard_url)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.welcome_email_subject, "New Subject!")

        # 2. Fire Broadcast (Mocked to prevent actual SMTP connection and async queueing)
        with patch("django_q.tasks.async_task") as mock_async:
            response2 = self.client.post(
                self.dashboard_url,
                {
                    "submit_broadcast": "true",
                    "broadcast_subject": "Hello",
                    "broadcast_body": "World",
                    "audience": "all",
                },
            )
            self.assertRedirects(response2, self.dashboard_url)

            # Prove the handoff to the background worker succeeded
            mock_async.assert_called_once()
            # Verify the correct task was queued
            self.assertEqual(
                mock_async.call_args[0][0], "farms.tasks.send_broadcast_email"
            )

    def test_edit_crop_invalid_data_graceful_fail(self):
        """Ensure editing a crop with blank data safely re-renders the form with errors."""
        from farms.models import Crop

        crop = Crop.objects.create(farm=self.farm, crop_name="Valid Crop")
        url = reverse("edit_crop", args=[crop.id])

        # Submit an empty crop name
        response = self.client.post(url, {"crop_name": "", "is_active": True})

        # Should NOT redirect (302). Must return 200 OK and show errors.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

        # Database should remain completely unchanged
        crop.refresh_from_db()
        self.assertEqual(crop.crop_name, "Valid Crop")

    def test_compliance_form_invalid_data_graceful_fail(self):
        """Ensure submitting a compliance form missing required legal text does not crash."""
        from farms.models import ComplianceForm

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_compliance_form": "true",
                "name": "Bad Form",
                "body_text": "",  # MISSING REQUIRED DATA
                "assignment_type": "all",
                "is_active": True,
            },
        )

        # Falls through the if is_valid() block and re-renders dashboard
        self.assertEqual(response.status_code, 200)
        self.assertIn("compliance_setup_form", response.context)
        self.assertTrue(response.context["compliance_setup_form"].errors)
        self.assertEqual(ComplianceForm.objects.count(), 0)

    def test_expired_trial_blocks_dashboard_modifications(self):
        """BUSINESS LOGIC: Ensure an expired trial locks the command center into read-only mode."""
        from datetime import timedelta
        from django.utils import timezone

        # Manually age the farm past the 60-day trial limit
        self.farm.created_at = timezone.now() - timedelta(days=65)
        self.farm.is_paid = False
        self.farm.save()

        self.client.force_login(self.manager)

        # Attempt to bypass the UI and add a crop via POST
        response = self.client.post(
            self.dashboard_url,
            {
                "submit_crop": "true",
                "crop_name": "Stolen Tomatoes",
                "is_active": True,
            },
        )

        # They should be bounced back to the dashboard with an error
        self.assertRedirects(response, self.dashboard_url)

        # Verify the database rejected the write
        from farms.models import Crop

        self.assertFalse(Crop.objects.filter(crop_name="Stolen Tomatoes").exists())


class VolunteerOnboardingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Public Test Farm", subscription_tier="growth"
        )

        # The Manager
        self.manager = User.objects.create_user(
            username="manager_bob",
            email="bob@test.com",
            password="p",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager, farm=self.farm, is_approved=True
        )

        # The Unattached Volunteer
        self.volunteer = User.objects.create_user(
            username="new_vol", email="vol@test.com", password="p", role="volunteer"
        )

        # NEW: Ensure the test farm is actually public so it appears in search!
        FarmProfile.objects.create(farm=self.farm, is_public=True)

    def test_magic_invite_link_auto_approves(self):
        """Ensure clicking the magic link bypasses the queue and auto-approves."""
        self.client.force_login(self.volunteer)
        url = reverse("invite_link", args=[self.farm.invite_token])

        response = self.client.get(url)
        self.assertRedirects(response, reverse("log_hours"))

        # Verify they are officially on the roster
        membership = FarmMembership.objects.get(user=self.volunteer, farm=self.farm)
        self.assertTrue(membership.is_approved)

    def test_farm_search_view(self):
        """Ensure unattached volunteers can search for farms."""
        self.client.force_login(self.volunteer)
        response = self.client.get(reverse("farm_search") + "?q=Public")

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.farm, response.context["farms"])

    def test_farm_search_hides_private_farms(self):
        """Ensure farms that have not opted into the public directory are hidden."""
        private_farm = Farm.objects.create(name="Private Hidden Farm")
        FarmProfile.objects.create(farm=private_farm, is_public=False)

        self.client.force_login(self.volunteer)
        response = self.client.get(reverse("farm_search") + "?q=Private")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(private_farm, response.context["farms"])

    def test_farm_search_respects_accepting_volunteers_toggle(self):
        """Ensure the 'Request to Join' button is hidden if the farm disables it."""
        self.farm.profile.is_accepting_volunteers = False
        self.farm.profile.save()

        self.client.force_login(self.volunteer)
        response = self.client.get(reverse("farm_search") + "?q=Public")

        # The farm should still show up in search
        self.assertIn(self.farm, response.context["farms"])

        # But the HTML should show the lockout message instead of the form
        self.assertContains(response, "Not accepting volunteers")
        self.assertNotContains(response, "Request to Join")

    def test_request_join_creates_pending_membership(self):
        """Ensure a public request puts the user in the pending queue."""
        self.client.force_login(self.volunteer)
        response = self.client.post(reverse("request_join", args=[self.farm.id]))

        self.assertRedirects(response, reverse("farm_search"))

        # Verify they are in the database, but NOT approved
        membership = FarmMembership.objects.get(user=self.volunteer, farm=self.farm)
        self.assertFalse(membership.is_approved)

    @patch("farms.views.send_volunteer_welcome_email")
    def test_manager_can_approve_request(self, mock_email):
        """Ensure a manager can approve a pending request and fire the welcome email."""
        # Setup a pending request
        membership = FarmMembership.objects.create(
            user=self.volunteer, farm=self.farm, is_approved=False
        )

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("approve_join", args=[membership.id]), {"action": "approve"}
        )

        self.assertRedirects(response, reverse("volunteer_roster"))
        membership.refresh_from_db()
        self.assertTrue(membership.is_approved)
        self.assertTrue(mock_email.called)

    def test_manager_can_deny_request(self):
        """Ensure denying a request permanently deletes the pending membership."""
        membership = FarmMembership.objects.create(
            user=self.volunteer, farm=self.farm, is_approved=False
        )

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("approve_join", args=[membership.id]), {"action": "deny"}
        )

        self.assertRedirects(response, reverse("volunteer_roster"))
        # The bridge record should be completely annihilated
        self.assertFalse(FarmMembership.objects.filter(id=membership.id).exists())

    def test_manager_cannot_approve_rival_farm_request(self):
        """SECURITY: Ensure Manager A cannot approve a request for Farm B (Cross-Tenant IDOR)."""
        # Create a rival farm and a pending request for it
        rival_farm = Farm.objects.create(name="Rival Farm", subscription_tier="growth")
        rival_membership = FarmMembership.objects.create(
            user=self.volunteer, farm=rival_farm, is_approved=False
        )

        # Log in as Manager of Farm A
        self.client.force_login(self.manager)

        # Try to approve the membership belonging to Farm B
        response = self.client.post(
            reverse("approve_join", args=[rival_membership.id]), {"action": "approve"}
        )

        # The get_object_or_404(..., farm=request.active_farm) should block it
        self.assertEqual(response.status_code, 404)

        # Verify the volunteer is STILL not approved for the rival farm
        rival_membership.refresh_from_db()
        self.assertFalse(rival_membership.is_approved)

    def test_volunteer_cannot_access_approval_queue(self):
        """SECURITY: Ensure standard volunteers cannot approve their own requests."""
        membership = FarmMembership.objects.create(
            user=self.volunteer, farm=self.farm, is_approved=False
        )

        # Log in as the unapproved volunteer
        self.client.force_login(self.volunteer)

        # Try to approve their own request
        response = self.client.post(
            reverse("approve_join", args=[membership.id]), {"action": "approve"}
        )

        # Should redirect them away (to the login/log-hours fallback)
        self.assertEqual(response.status_code, 302)
        membership.refresh_from_db()
        self.assertFalse(membership.is_approved)

    def test_magic_link_handles_already_approved_users(self):
        """STABILITY: Ensure clicking the invite link twice doesn't crash the database with UniqueConstraint errors."""
        self.client.force_login(self.volunteer)
        url = reverse("invite_link", args=[self.farm.invite_token])

        # Click 1: Joins the farm
        self.client.get(url)

        # Click 2: Should safely handle the duplicate
        response = self.client.get(url)

        self.assertRedirects(response, reverse("log_hours"))
        # Verify there is still only ONE membership record for this user/farm combo
        self.assertEqual(
            FarmMembership.objects.filter(user=self.volunteer, farm=self.farm).count(),
            1,
        )

    def test_magic_link_404s_on_invalid_token(self):
        """PRIVACY: Ensure guessing a random UUID doesn't grant access to a farm."""
        import uuid

        self.client.force_login(self.volunteer)

        fake_token = uuid.uuid4()
        url = reverse("invite_link", args=[fake_token])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_request_join_with_message_saves_correctly(self):
        """MARKETPLACE: Ensure a volunteer can send an introductory message with their application."""
        self.client.force_login(self.volunteer)
        application_message = (
            "I have 3 years of organic farming experience and love tomatoes!"
        )

        response = self.client.post(
            reverse("request_join", args=[self.farm.id]),
            {"applicant_message": application_message},
        )

        self.assertRedirects(response, reverse("farm_search"))

        # Verify the message reached the database
        membership = FarmMembership.objects.get(user=self.volunteer, farm=self.farm)
        self.assertEqual(membership.applicant_message, application_message)
        self.assertFalse(membership.is_approved)

    def test_reapplying_updates_applicant_message(self):
        """MARKETPLACE: Ensure subsequent join requests update the message if the user is still pending."""
        # Create an initial pending membership
        FarmMembership.objects.create(
            user=self.volunteer,
            farm=self.farm,
            is_approved=False,
            applicant_message="Old message",
        )

        self.client.force_login(self.volunteer)
        new_message = "Updated availability: I can now work weekends!"

        self.client.post(
            reverse("request_join", args=[self.farm.id]),
            {"applicant_message": new_message},
        )

        membership = FarmMembership.objects.get(user=self.volunteer, farm=self.farm)
        self.assertEqual(membership.applicant_message, new_message)

    def test_manager_roster_displays_applicant_message(self):
        """UI: Ensure the Farm Manager can physically see the applicant's message in the roster."""
        # Create a pending applicant with a message
        msg = "Hi, I am looking to fulfill my 80-hour commitment here."
        FarmMembership.objects.create(
            user=self.volunteer,
            farm=self.farm,
            is_approved=False,
            applicant_message=msg,
        )

        self.client.force_login(self.manager)
        # Set the session so the roster knows which farm we are managing
        session = self.client.session
        session["active_farm_id"] = self.farm.id
        session.save()

        response = self.client.get(reverse("volunteer_roster"))

        # Verify the message appears in the HTML context
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, msg)
        self.assertContains(response, self.volunteer.email)

    def test_end_to_end_marketplace_application(self):
        """STABILITY: Ensure a message-backed application flows perfectly to the Manager Roster."""
        # 1. Setup a public farm
        self.farm.profile.is_public = True
        self.farm.profile.save()

        # 2. Volunteer applies with a custom note
        self.client.force_login(self.volunteer)
        app_note = "I grew up on a cherry farm and want to help with your harvest."
        self.client.post(
            reverse("request_join", args=[self.farm.id]),
            {"applicant_message": app_note},
        )

        # 3. Manager views the roster to see the 'package'
        self.client.force_login(self.manager)
        session = self.client.session
        session["active_farm_id"] = self.farm.id
        session.save()

        response = self.client.get(reverse("volunteer_roster"))

        # 4. Verify the Manager sees the pitch AND the volunteer details
        self.assertContains(response, app_note)
        self.assertContains(
            response, self.volunteer.get_full_name() or self.volunteer.username
        )
        self.assertContains(response, "Applicants")

    def test_privacy_anonymous_users_cannot_view_directory(self):
        """PRIVACY: Ensure unauthenticated internet traffic cannot scrape the directory."""
        # Ensure the test client is completely logged out
        self.client.logout()

        # Attempt to access the search page
        search_response = self.client.get(reverse("farm_search"))
        # Attempt to access a specific public profile
        detail_response = self.client.get(
            reverse("public_farm_detail", args=[self.farm.id])
        )

        # Both should trigger a 302 Redirect to the login screen, NOT a 200 OK
        self.assertEqual(search_response.status_code, 302)
        self.assertEqual(detail_response.status_code, 302)
        self.assertTrue(search_response.url.startswith("/accounts/login/"))

    def test_search_system_deep_field_querying(self):
        """SEARCH: Ensure Q objects successfully query related FarmProfile fields."""
        self.client.force_login(self.volunteer)

        # Create a farm with a completely unrelated name, but specific perks/tags
        stealth_farm = Farm.objects.create(name="Generic Operations LLC")
        FarmProfile.objects.create(
            farm=stealth_farm,
            is_public=True,
            volunteer_perks="Free helicopter rides",
            tags='[{"value":"Hydroponic"}]',
        )

        # Search for the perk
        perk_response = self.client.get(reverse("farm_search") + "?q=helicopter")
        self.assertIn(stealth_farm, perk_response.context["farms"])

        # Search for the tag
        tag_response = self.client.get(reverse("farm_search") + "?q=Hydroponic")
        self.assertIn(stealth_farm, tag_response.context["farms"])

    def test_search_system_enforces_query_limits(self):
        """STABILITY: Ensure the database doesn't crash by attempting to render hundreds of farms."""
        self.client.force_login(self.volunteer)

        # Create 16 public farms with the exact same name
        for i in range(16):
            bulk_farm = Farm.objects.create(name="Limit Test Farm")
            FarmProfile.objects.create(farm=bulk_farm, is_public=True)

        response = self.client.get(reverse("farm_search") + "?q=Limit")

        # The query should strictly slice the results to 15 to protect server memory
        self.assertEqual(len(response.context["farms"]), 15)


class EdgeCaseDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a manager but DO NOT give them a FarmMembership
        self.homeless_manager = User.objects.create_user(
            username="nomad",
            email="nomad@test.com",
            password="pass",
            role="farm_manager",
        )

    def test_manager_dashboard_without_farm_redirects(self):
        """Covers Lines 44-48: Ensure managers without a farm are safely caught and redirected."""
        self.client.force_login(self.homeless_manager)
        response = self.client.get(reverse("manager_dashboard"))

        # Should redirect to the home page since they aren't staff
        self.assertRedirects(response, "/")

        # Verify the error message was generated
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertIn("You are not linked to a farm", str(messages[0]))


class FarmProfileGalleryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Gallery Farm")
        self.manager = User.objects.create_user(
            username="gallery_mgr",
            email="gal@test.com",
            password="p",
            role="farm_manager",
        )
        FarmMembership.objects.create(
            user=self.manager, farm=self.farm, is_approved=True
        )
        self.profile = FarmProfile.objects.create(farm=self.farm)

        # Create a dummy image for testing
        self.dummy_image = SimpleUploadedFile(
            name="test_image.jpg",
            content=b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b",
            content_type="image/jpeg",
        )

    def test_manager_can_delete_gallery_image(self):
        """Covers Lines 203-204: Image deletion path."""
        self.client.force_login(self.manager)
        img = FarmImage.objects.create(profile=self.profile, image="dummy.jpg")

        response = self.client.post(
            reverse("edit_farm_profile"), {"delete_image": str(img.id)}
        )
        self.assertRedirects(response, reverse("edit_farm_profile"))
        self.assertEqual(FarmImage.objects.filter(profile=self.profile).count(), 0)

    def test_manager_gallery_upload_limit_enforced(self):
        """NUCLEAR DIAGNOSTIC 2.0: Validates the newly patched MultipleFileField."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.manager)

        # Max out the gallery manually first
        for i in range(5):
            FarmImage.objects.create(profile=self.profile, image=f"dummy_{i}.jpg")

        fresh_image = SimpleUploadedFile(
            name="test_image.jpg",
            content=b"dummy image content",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("edit_farm_profile"),
            {
                "submit_profile": "true",
                "is_public": True,
                "short_description": "Valid description.",
                "about_us": "<div>About us</div>",
                "tags": '[{"value":"Organic"}]',
                "website_url": "https://" + "example.com",
                "volunteer_perks": "Free vegetables.",
                "physical_requirements": "Ability to lift 30 lbs.",
                # The test client puts this in a list, which our new form field can finally read!
                "gallery_uploads": [fresh_image],
            },
        )

        # =====================================================================
        # ☢️ THE AUTOPSY TRIPWIRE ☢️
        # =====================================================================
        if response.status_code == 200:
            error_log = [
                "\n\n☢️ FORM VALIDATION FAILED (200 OK instead of 302 Redirect) ☢️\n"
            ]

            req = getattr(response, "wsgi_request", None)
            if req:
                error_log.append("--- SERVER RECEIVED FILES ---")
                error_log.append(str(req.FILES))

            if "profile_form" in response.context:
                form = response.context["profile_form"]
                error_log.append("\n--- EXACT FIELD ERRORS ---")
                error_log.append(form.errors.as_json())

            error_log.append(
                "\n=====================================================================\n"
            )
            self.fail("\n".join(error_log))
        # =====================================================================

        self.assertRedirects(response, reverse("edit_farm_profile"))
        self.assertEqual(FarmImage.objects.filter(profile=self.profile).count(), 5)


class PublicDirectoryTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.public_farm = Farm.objects.create(name="Happy Valley Farms")
        self.public_profile = FarmProfile.objects.create(
            farm=self.public_farm, is_public=True
        )

        self.private_farm = Farm.objects.create(name="Secret Valley Farms")
        self.private_profile = FarmProfile.objects.create(
            farm=self.private_farm, is_public=False
        )

        # THE FIX: Add an email so the RequireEmailMiddleware doesn't intercept the request!
        self.volunteer = User.objects.create_user(
            username="stat_vol",
            email="stat_vol@test.com",
            password="p",
            role="volunteer",
        )
        self.crop = Crop.objects.create(farm=self.public_farm, crop_name="Corn")

        # Create a log entry to test the Plotly chart aggregation
        LogEntry.objects.create(
            farm=self.public_farm,
            volunteer=self.volunteer,
            crop=self.crop,
            duration_hours=5.5,
            activity="H",
            date_logged="2026-05-20",
        )

        # Clear cache before tests to ensure fresh stats
        cache.clear()

    def test_live_stats_fragment_caching(self):
        """Covers the global live stats generator and caching."""
        # Ensure url name matches your urls.py (adjust to 'live_stats' if needed)
        response = self.client.get(reverse("live_stats_fragment"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("stats", response.context)

        # Verify it successfully cached
        self.assertIsNotNone(cache.get("landing_page_stats"))

    def test_public_farm_detail_generates_plotly_data(self):
        """Covers Lines 865-958: The public resume page and the Plotly dictionary builder."""
        self.client.force_login(self.volunteer)

        # Ensure url name matches your urls.py (adjust if needed)
        url = reverse("public_farm_detail", args=[self.public_farm.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "farms/public_farm_detail.html")

        # Verify the context generated the JSON required for Plotly to render
        self.assertIn("plotly_traces_json", response.context)
        self.assertIn("Corn", response.context["plotly_traces_json"])

    def test_public_farm_detail_404s_for_private_farms(self):
        """Ensures volunteers cannot view profiles of farms that opted out of the directory."""
        self.client.force_login(self.volunteer)

        url = reverse("public_farm_detail", args=[self.private_farm.id])
        response = self.client.get(url)

        # The get_object_or_404 should catch it and throw a 404
        self.assertEqual(response.status_code, 404)
