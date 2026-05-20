from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm, ComplianceForm
from accounts.models import FarmMembership, FormSignature

User = get_user_model()


class LoginActionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Schuler Test Farm")

        self.user = User.objects.create_user(
            username="test_volunteer",
            email="test_vol@example.com",
            password="my_secure_password123",
        )
        FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True, agreed_to_waiver=True
        )
        self.login_url = reverse("login")

    def test_successful_login_redirects(self):
        response = self.client.post(
            self.login_url,
            {"username": "test_volunteer", "password": "my_secure_password123"},
        )
        self.assertRedirects(response, "/log-hours/", target_status_code=200)

    def test_failed_login_shows_error(self):
        response = self.client.post(
            self.login_url, {"username": "test_volunteer", "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your username and password didn't match")


class ProfileViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Test Farm")

        self.user = User.objects.create_user(
            username="profile_tester",
            email="profile_tester@example.com",
            password="testpass123",
        )
        FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True, agreed_to_waiver=True
        )
        self.client.force_login(self.user)

    def test_profile_view_get(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_view_post_valid(self):
        post_data = {
            "username": self.user.username,
            "first_name": "Updated",
            "last_name": "Name",
            "email": "test@example.com",
        }
        response = self.client.post(reverse("profile"), post_data)
        self.assertRedirects(response, reverse("profile"))

    def test_upload_avatar_post(self):
        dummy_base64_image = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
            "HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        response = self.client.post(
            reverse("upload_avatar"), {"avatar_base64": dummy_base64_image}
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))

    def test_upload_avatar_post_empty(self):
        """Covers lines 61-64: Missing base64 data."""
        response = self.client.post(reverse("upload_avatar"), {})
        self.assertRedirects(response, reverse("profile"))

    def test_profile_view_rejects_invalid_phone(self):
        """Ensure the profile form strictly validates phone numbers."""
        post_data = {
            "username": self.user.username,
            "first_name": "Updated",
            "last_name": "Name",
            "email": "test@example.com",
            "phone_number": "Not a real number",
        }
        response = self.client.post(reverse("profile"), post_data)

        # It should bounce back to the form (200), not redirect (302)
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone_number", response.context["form"].errors)

    def test_profile_view_displays_signed_documents(self):
        """Phase 3: Ensure signed documents are passed to the profile context."""
        from farms.models import ComplianceForm
        from accounts.models import FormSignature

        # Give them a signed form
        form = ComplianceForm.objects.create(
            farm=self.farm, name="Test Doc", body_text="text"
        )
        FormSignature.objects.create(
            user=self.user, form=form, digital_signature="Test Name"
        )

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("signatures", response.context)
        self.assertEqual(response.context["signatures"].count(), 1)


class LegacyClaimFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Legacy Farm")

        self.ghost_user = User.objects.create(
            username="john_doe", first_name="John", last_name="Doe", email=""
        )
        self.ghost_user.set_unusable_password()
        self.ghost_user.save()

        self.claimed_user = User.objects.create_user(
            username="jane_doe",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            password="securepassword",
        )
        self.search_url = reverse("claim_search")
        self.setup_url = reverse("claim_setup", args=[self.ghost_user.id])

    def test_search_finds_unclaimed_account(self):
        response = self.client.post(self.search_url, {"search_name": "John"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.ghost_user, response.context["matches"])

    def test_search_fails_gracefully_on_no_match(self):
        response = self.client.post(self.search_url, {"search_name": "Ghostbuster"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["matches"])

    def test_setup_secures_account_and_logs_in(self):
        response = self.client.post(
            self.setup_url,
            {
                "email": "john.doe@newemail.com",
                "password": "newsecurepassword123",
                "confirm_password": "newsecurepassword123",
            },
        )
        self.assertRedirects(response, reverse("log_hours"))
        self.ghost_user.refresh_from_db()
        self.assertEqual(self.ghost_user.email, "john.doe@newemail.com")
        self.assertTrue(self.ghost_user.has_usable_password())

    def test_setup_rejects_mismatched_passwords(self):
        """Ensures the AccountClaimForm catches mismatched passwords."""
        response = self.client.post(
            self.setup_url,
            {
                "email": "john.doe@newemail.com",
                "password": "securepassword123",
                "confirm_password": "differentpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match.")

    def test_claim_account_setup_get(self):
        """Covers line 140: GET request for claim setup."""
        response = self.client.get(self.setup_url)
        self.assertEqual(response.status_code, 200)


class EmailTollboothTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Tollbooth Farm")
        self.no_email_user = User.objects.create_user(
            username="no_email_guy", email="", password="securepassword"
        )
        FarmMembership.objects.create(
            user=self.no_email_user, farm=self.farm, is_approved=True
        )
        self.update_url = reverse("update_email")

    def test_tollbooth_forces_redirect_for_missing_email(self):
        self.client.force_login(self.no_email_user)
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, self.update_url)

    def test_successful_email_update_clears_tollbooth(self):
        self.client.force_login(self.no_email_user)
        response = self.client.post(
            self.update_url, {"email": "nowihaveanemail@example.com"}
        )
        self.assertRedirects(response, "/")
        self.no_email_user.refresh_from_db()
        self.assertEqual(self.no_email_user.email, "nowihaveanemail@example.com")

    def test_email_middleware_allows_static_assets(self):
        self.client.force_login(self.no_email_user)
        from django.conf import settings

        response = self.client.get(f"{settings.STATIC_URL}css/dist/styles.css")
        self.assertNotEqual(response.status_code, 302)

    def test_email_tollbooth_allows_logout(self):
        """Ensure users trapped by the email tollbooth can still log out."""
        self.client.force_login(self.no_email_user)
        response = self.client.post(reverse("logout"))
        if hasattr(response, "url"):
            self.assertNotEqual(response.url, reverse("update_email"))

    def test_update_email_post_empty(self):
        """Covers line 84: Empty email submitted."""
        self.client.force_login(self.no_email_user)
        response = self.client.post(self.update_url, {"email": "   "})
        self.assertEqual(response.status_code, 200)


class ComplianceGateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Strict Liability Farm")

        self.compliance_form = ComplianceForm.objects.create(
            farm=self.farm,
            name="2026 Safety Waiver",
            body_text="You must sign this to enter.",
            is_active=True,
            assignment_type="all",
        )

        self.user = User.objects.create_user(
            username="test_volunteer",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="securepassword",
        )
        self.membership = FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True
        )
        self.client.force_login(self.user)

    def test_middleware_redirects_to_waiver(self):
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_successful_signature_unlocks_account(self):
        response = self.client.post(reverse("sign_waiver"), {"signature": "John Doe"})
        self.assertRedirects(response, reverse("log_hours"))

        signature_exists = FormSignature.objects.filter(
            user=self.user, form=self.compliance_form
        ).exists()
        self.assertTrue(signature_exists)

    def test_waiver_get_request_renders_form(self):
        response = self.client.get(reverse("sign_waiver"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/sign_waiver.html")

    def test_waiver_rejects_wrong_name(self):
        response = self.client.post(reverse("sign_waiver"), {"signature": "Wrong Name"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Your signature must match your first and last name exactly."
        )
        signature_exists = FormSignature.objects.filter(user=self.user).exists()
        self.assertFalse(signature_exists)

    def test_waiver_middleware_allows_static_assets(self):
        from django.conf import settings

        response = self.client.get(f"{settings.STATIC_URL}css/dist/styles.css")
        self.assertNotEqual(response.status_code, 302)

    def test_waiver_redirects_if_none_pending(self):
        FormSignature.objects.create(
            user=self.user, form=self.compliance_form, digital_signature="John Doe"
        )
        response = self.client.get(reverse("sign_waiver"))
        self.assertRedirects(response, reverse("log_hours"))

    def test_waiver_handles_multiple_forms(self):
        ComplianceForm.objects.create(
            farm=self.farm,
            name="Second Form",
            body_text="Another one",
            is_active=True,
            assignment_type="all",
        )
        response = self.client.post(reverse("sign_waiver"), {"signature": "John Doe"})
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_specific_assignment_waiver_logic(self):
        self.compliance_form.assignment_type = "specific"
        self.compliance_form.save()

        response = self.client.get(reverse("log_hours"))
        self.assertEqual(response.status_code, 200)

        self.compliance_form.assigned_users.add(self.user)
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_legacy_friend_bypasses_waiver(self):
        """Ensure read-only legacy friends are not trapped by the tollbooth."""
        self.user.role = "friend"
        self.user.save()

        response = self.client.get(reverse("log_hours"))
        self.assertEqual(response.status_code, 200)

    def test_waiver_middleware_allows_logout(self):
        """Ensure users trapped by the waiver can still log out."""
        response = self.client.post(reverse("logout"))
        if hasattr(response, "url"):
            self.assertNotEqual(response.url, reverse("sign_waiver"))

    def test_waiver_accepts_guardian_signature(self):
        """Phase 2: Ensure a parent can sign for a minor without matching the account name."""
        response = self.client.post(
            reverse("sign_waiver"),
            {
                "is_guardian": "on",
                "guardian_relationship": "Mother",
                "signature": "Jane Doe",  # Purposely does NOT match the volunteer's name
            },
        )
        # Should succeed and unlock the app
        self.assertRedirects(response, reverse("log_hours"))

        # Verify the database caught the guardian metadata
        sig = FormSignature.objects.get(user=self.user, form=self.compliance_form)
        self.assertTrue(sig.is_guardian_signature)
        self.assertEqual(sig.guardian_relationship, "Mother")
        self.assertEqual(sig.digital_signature, "Jane Doe")

    def test_waiver_rejects_guardian_without_relationship(self):
        """Phase 2: Ensure we mandate the relationship field for guardians."""
        response = self.client.post(
            reverse("sign_waiver"),
            {
                "is_guardian": "on",
                "guardian_relationship": "",  # Missing!
                "signature": "Jane Doe",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please specify your relationship")
