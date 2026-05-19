from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import CustomUser, FarmMembership
from farms.models import Farm, Crop
from logs.models import LogEntry


class AnalyticsViewsTest(TestCase):
    def setUp(self):
        # 1. Create a dummy farm and user
        self.farm = Farm.objects.create(name="Test Farm")

        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="analytics_tester@example.com",
            password="testpass",
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        # 2. Create a dummy crop
        self.crop = Crop.objects.create(
            crop_name="Tomatoes", category="Nightshades", farm=self.farm
        )

        # 3. Create a dummy log entry so Pandas has data to crunch!
        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            crop=self.crop,
            activity="P",  # P for Planting
            duration_hours=2.5,
            date_logged=timezone.now().date(),
        )

    def test_impact_chart_loads_with_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("get_impact_chart"))
        self.assertEqual(response.status_code, 200)

    def test_heatmap_loads_with_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("get_activity_heatmap"))
        self.assertEqual(response.status_code, 200)

    def test_term_heatmap_loads_with_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("get_term_heatmap"))
        self.assertEqual(response.status_code, 200)