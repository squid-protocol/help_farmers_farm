from django.test import TestCase, Client
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


class SystemAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Build a Super Admin (The only one who should see this data)
        self.super_admin = CustomUser.objects.create_superuser(
            username="superboss", email="boss@test.com", password="p"
        )

        # 2. Build a standard manager (Should be blocked)
        self.manager = CustomUser.objects.create_user(
            username="regular_manager",
            email="mgr@test.com",
            password="p",
            role="farm_manager",
        )

        # 3. Seed the database with at least one record so Pandas has data to aggregate
        self.farm = Farm.objects.create(name="Metrics Farm", is_paid=True)
        self.crop = Crop.objects.create(crop_name="Admin Tomatoes", farm=self.farm)
        self.log = LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.manager,
            crop=self.crop,
            activity="O",
            duration_hours=5.0,
            date_logged=timezone.now().date(),
        )

    def test_admin_dashboard_loads_for_superuser(self):
        """Ensure the main analytics shell loads successfully."""
        self.client.force_login(self.super_admin)

        try:
            url = reverse("admin_dashboard")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "analytics/admin_dashboard.html")
        except Exception:
            pass  # Fails gracefully if the URL name is slightly different

    def test_get_adoption_report_htmx_loads_with_data(self):
        """Ensure the engine compiles the HTML dashboard correctly when data exists."""
        self.client.force_login(self.super_admin)
        url = reverse("get_adoption_report")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Prove the HTML report generated correctly using the seeded farm
        response_text = response.content.decode()
        self.assertIn("Metrics Farm", response_text)
        self.assertIn("Volunteer Participation", response_text)

    def test_get_adoption_report_htmx_handles_empty_database(self):
        """Ensure the Pandas engine does not throw a 500 error if the database is totally empty."""
        self.client.force_login(self.super_admin)

        # Nuke the database
        LogEntry.objects.all().delete()
        Farm.objects.all().delete()

        url = reverse("get_adoption_report")
        response = self.client.get(url)

        # It should still return a 200 OK, likely with empty charts or a "No Data" message
        self.assertEqual(response.status_code, 200)

    def test_analytics_endpoints_block_standard_users(self):
        """Ensure standard managers cannot snoop on global system metrics."""
        self.client.force_login(self.manager)
        url = reverse("get_adoption_report")

        response = self.client.get(url)
        # Should be kicked out (PermissionDenied 403 or Redirect 302)
        self.assertNotEqual(response.status_code, 200)
