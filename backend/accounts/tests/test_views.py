from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm

User = get_user_model()

class LoginActionTests(TestCase):
    def setUp(self):
        # 1. Arrange: Create our "invisible browser" and a test user
        self.client = Client()
        self.farm = Farm.objects.create(name="Schuler Test Farm")
        self.user = User.objects.create_user(
            username="test_volunteer", 
            password="my_secure_password123",
            farm=self.farm
        )
        self.login_url = reverse('login')

    def test_successful_login_redirects(self):
        # 2. Act: The invisible browser submits the login form
        response = self.client.post(self.login_url, {
            'username': 'test_volunteer',
            'password': 'my_secure_password123'
        })

        # 3. Assert: It should redirect (HTTP 302) to the log-hours page
        self.assertRedirects(response, '/log-hours/', target_status_code=200)

    def test_failed_login_shows_error(self):
        # 2. Act: The invisible browser submits the WRONG password
        response = self.client.post(self.login_url, {
            'username': 'test_volunteer',
            'password': 'wrongpassword'
        })

        # 3. Assert: It should NOT redirect (stays on login page, HTTP 200)
        self.assertEqual(response.status_code, 200)
        # And we check if our custom error message is in the HTML
        self.assertContains(response, "Your username and password didn't match")