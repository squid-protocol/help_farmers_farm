from django.test import TestCase
from django.urls import reverse
from accounts.models import CustomUser
from farms.models import Farm

class AnalyticsViewsTest(TestCase):
    def setUp(self):
        # Create a dummy farm and user to bypass the @login_required decorators
        self.farm = Farm.objects.create(name="Test Farm")
        self.user = CustomUser.objects.create_user(username="testuser", password="testpass", farm=self.farm)

    def test_impact_chart_loads(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse('get_impact_chart'))
        self.assertEqual(response.status_code, 200)

    def test_heatmap_loads(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse('get_activity_heatmap'))
        self.assertEqual(response.status_code, 200)

    def test_term_heatmap_loads(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse('get_term_heatmap'))
        self.assertEqual(response.status_code, 200)