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
        self.crop = Crop.objects.create(crop_name="Tomatoes", category="Nightshades", farm=self.farm)

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

    def test_starter_tier_cannot_export_enterprise_csv(self):
        """BUSINESS LOGIC: Ensure lower tiers cannot bypass the UI to download grant reports."""
        self.farm.subscription_tier = "starter"
        self.farm.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("export_grant_report"))

        # They should be kicked back to the dashboard, NOT given a CSV download
        self.assertRedirects(response, reverse("manager_dashboard"), fetch_redirect_response=False)

    def test_enterprise_tier_can_export_csv(self):
        """BUSINESS LOGIC: Ensure paying Enterprise users receive the CSV file."""
        self.farm.subscription_tier = "institutional"
        self.farm.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("export_grant_report"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", response["Content-Disposition"])


class SystemAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.super_admin = CustomUser.objects.create_superuser(
            username="superboss", email="boss@test.com", password="p"
        )

        self.manager = CustomUser.objects.create_user(
            username="regular_manager",
            email="mgr@test.com",
            password="p",
            role="farm_manager",
        )

        self.farm = Farm.objects.create(name="Metrics Farm", is_paid=True)
        self.crop = Crop.objects.create(crop_name="Admin Tomatoes", farm=self.farm)
        LogEntry.objects.create(
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
        url = reverse("admin_adoption_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "analytics/admin_dashboard.html")

    def test_get_adoption_report_htmx_loads_with_data(self):
        """Ensure the engine compiles the HTML dashboard correctly when data exists."""
        self.client.force_login(self.super_admin)
        url = reverse("get_adoption_report")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Metrics Farm", response.content.decode())

    def test_get_adoption_report_htmx_handles_empty_database(self):
        """Ensure the Pandas engine does not throw a 500 error if the database is totally empty."""
        self.client.force_login(self.super_admin)
        LogEntry.objects.all().delete()
        Farm.objects.all().delete()

        url = reverse("get_adoption_report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_analytics_endpoints_block_standard_users(self):
        """Ensure standard managers cannot snoop on global system metrics."""
        self.client.force_login(self.manager)
        url = reverse("get_adoption_report")
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)


class AnalyticsEmptyStateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Empty Farm")
        self.user = CustomUser.objects.create_user(username="manager", email="manager@test.com", password="p")
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        session = self.client.session
        session["active_farm_id"] = self.farm.id
        session.save()

        self.client.force_login(self.user)

    def test_all_charts_handle_empty_data_gracefully(self):
        """Ensure Pandas does not crash when a farm has zero logs."""
        endpoints = [
            "get_impact_chart",
            "get_activity_heatmap",
            "get_term_heatmap",
            "get_seasonal_timeline",
            "get_volunteer_heatmap",
        ]

        for endpoint in endpoints:
            response = self.client.get(reverse(endpoint))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "div")

    def test_analytics_handle_null_crops_without_crashing(self):
        """Ensure Pandas correctly catches and labels logs that have no crop assigned."""
        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            crop=None,
            activity="O",
            duration_hours=1.5,
            date_logged=timezone.now().date(),
        )

        endpoints = [
            "get_impact_chart",
            "get_activity_heatmap",
            "get_term_heatmap",
            "get_seasonal_timeline",
        ]

        for endpoint in endpoints:
            response = self.client.get(reverse(endpoint))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "General / Deleted")

    def test_impact_chart_returns_empty_state_for_new_farm(self):
        """STABILITY: Ensure a new farm without logs sees a clean 'no data' message instead of a 500 error."""
        response = self.client.get(reverse("get_impact_chart"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("No hours logged", response.content.decode())

    def test_analytics_work_for_unpaid_farms(self):
        """STABILITY: Unpaid farms in 'Read-Only' mode must still be able to see their historical data."""
        self.farm.is_paid = False
        self.farm.save()

        # Add historical data
        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            duration_hours=10.0,
            date_logged="2025-01-01",
            activity="T",
        )

        response = self.client.get(reverse("get_impact_chart") + "?year=2025")
        self.assertEqual(response.status_code, 200)
        self.assertIn("10", response.content.decode())
