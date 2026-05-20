from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm
from accounts.models import FarmMembership

User = get_user_model()


class LoginActionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Schuler Test Farm")

        # Create user WITHOUT the farm keyword
        self.user = User.objects.create_user(
            username="test_volunteer",
            email="test_vol@example.com",
            password="my_secure_password123",
        )
        # Create the bridge!
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True, agreed_to_waiver=True)

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
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True, agreed_to_waiver=True)
        self.client.force_login(self.user)

    def test_profile_view_get(self):
        """Tests that the profile page loads successfully."""
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_view_post_valid(self):
        """Tests submitting a valid profile update."""
        post_data = {
            "username": self.user.username,
            "first_name": "Updated",
            "last_name": "Name",
            "email": "test@example.com",
        }
        response = self.client.post(reverse("profile"), post_data)
        self.assertRedirects(response, reverse("profile"))

    def test_upload_avatar_post(self):
        """Tests uploading an avatar via base64 data."""
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


class LegacyClaimFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Legacy Farm")
        
        # Ghost account (no email)
        self.ghost_user = User.objects.create(
            username="john_doe",
            first_name="John",
            last_name="Doe",
            email="" 
        )
        self.ghost_user.set_unusable_password()
        self.ghost_user.save()
        
        # Claimed account
        self.claimed_user = User.objects.create_user(
            username="jane_doe",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            password="securepassword"
        )
        self.search_url = reverse("claim_search")
        self.setup_url = reverse("claim_setup", args=[self.ghost_user.id])

    def test_search_finds_unclaimed_account(self):
        response = self.client.post(self.search_url, {"search_name": "John"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.ghost_user, response.context["matches"])
        self.assertNotIn(self.claimed_user, response.context["matches"])

    def test_search_fails_gracefully_on_no_match(self):
        response = self.client.post(self.search_url, {"search_name": "Ghostbuster"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["matches"])

    def test_setup_secures_account_and_logs_in(self):
        response = self.client.post(self.setup_url, {
            "email": "john.doe@newemail.com",
            "password": "newsecurepassword123",
            "confirm_password": "newsecurepassword123"
        })
        self.assertRedirects(response, reverse("log_hours"))
        self.ghost_user.refresh_from_db()
        self.assertEqual(self.ghost_user.email, "john.doe@newemail.com")
        self.assertTrue(self.ghost_user.has_usable_password())


class EmailTollboothTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Tollbooth Farm")
        self.no_email_user = User.objects.create_user(
            username="no_email_guy",
            email="",
            password="securepassword"
        )
        FarmMembership.objects.create(user=self.no_email_user, farm=self.farm, is_approved=True)
        self.update_url = reverse("update_email")

    def test_tollbooth_forces_redirect_for_missing_email(self):
        self.client.force_login(self.no_email_user)
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, self.update_url)

    def test_successful_email_update_clears_tollbooth(self):
        self.client.force_login(self.no_email_user)
        response = self.client.post(self.update_url, {
            "email": "nowihaveanemail@example.com"
        })
        self.assertRedirects(response, "/")
        self.no_email_user.refresh_from_db()
        self.assertEqual(self.no_email_user.email, "nowihaveanemail@example.com")


class ComplianceGateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Strict Liability Farm",
            liability_waiver_text="You must sign this to enter."
        )
        self.user = User.objects.create_user(
            username="test_volunteer",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="securepassword"
        )
        # Approved, but NO waiver signature yet
        self.membership = FarmMembership.objects.create(
            user=self.user, 
            farm=self.farm, 
            is_approved=True,
            agreed_to_waiver=False 
        )
        self.client.force_login(self.user)

    def test_middleware_redirects_to_waiver(self):
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_successful_signature_unlocks_account(self):
        response = self.client.post(reverse("sign_waiver"), {
            "signature": "John Doe"
        })
        self.assertRedirects(response, reverse("log_hours"))
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.agreed_to_waiver)
        self.assertIsNotNone(self.membership.signed_at)