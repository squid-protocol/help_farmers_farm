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
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

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
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        # Force the test client to log in
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

        if response.status_code == 200:
            print("\n--- FORM VALIDATION FAILED ---")
            print(response.context["form"].errors)
            print("------------------------------\n")

        # Check that it redirects back to the profile page on success
        self.assertRedirects(response, reverse("profile"))

    def test_upload_avatar_post(self):
        """Tests uploading an avatar via base64 data."""
        # This is a tiny 1x1 pixel transparent PNG encoded in base64
        dummy_base64_image = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
            "HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )

        response = self.client.post(
            reverse("upload_avatar"), {"avatar_base64": dummy_base64_image}
        )

        # Check that it redirects back to the profile page
        self.assertRedirects(response, reverse("profile"))

        # Verify the avatar was actually saved to the user model
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))
