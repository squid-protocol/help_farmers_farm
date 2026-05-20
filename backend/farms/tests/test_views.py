from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm, Crop
from accounts.models import FarmMembership

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

    def test_manager_can_view_own_volunteer(self):
        self.client.force_login(self.manager_a)
        url = reverse("volunteer_detail", args=[self.volunteer_a.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_view_rival_volunteer_idor(self):
        self.client.force_login(self.manager_a)
        url = reverse("volunteer_detail", args=[self.volunteer_b.id])
        response = self.client.get(url)

        # THE FIX: Expect a 403 Forbidden instead of a 404 Not Found
        self.assertEqual(response.status_code, 403)

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
        self.farm = Farm.objects.create(name="Action Test Farm")

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

    def test_manager_can_create_commitment(self):
        self.client.force_login(self.manager)
        from farms.models import WorkCommitment

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

    def test_manager_can_update_farm_settings(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.dashboard_url,
            {
                "submit_farm_settings": "true",
                "name": "Updated Farm Name",
                "season_start": "2026-05-01",
                "season_end": "2026-10-31",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, "Updated Farm Name")
