from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm

User = get_user_model()

class SecurityIDORTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Build Farm A (The Good Guys)
        self.farm_a = Farm.objects.create(name="Schuler Test Farm")

        # THE FIX: Added emails to all users
        self.manager_a = User.objects.create_user(
            username="manager_a",
            email="manager_a@example.com",
            password="secure",
            farm=self.farm_a,
            role="farm_manager",  
        )

        self.volunteer_a = User.objects.create_user(
            username="vol_a", 
            email="vol_a@example.com",
            password="secure", 
            farm=self.farm_a
        )

        # 2. Build Farm B (The Rivals)
        self.farm_b = Farm.objects.create(name="Rival Valley Farms")
        self.volunteer_b = User.objects.create_user(
            username="vol_b", 
            email="vol_b@example.com",
            password="secure", 
            farm=self.farm_b
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
        self.assertEqual(response.status_code, 404)

    def test_manager_cannot_delete_rival_volunteer(self):
        self.client.force_login(self.manager_a)
        url = reverse("remove_user", args=[self.volunteer_b.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(id=self.volunteer_b.id).exists())

    def test_manager_cannot_delete_another_manager(self):
        # THE FIX: Added email here too
        manager_a2 = User.objects.create_user(
            username="manager_a2",
            email="manager_a2@example.com",
            password="secure",
            farm=self.farm_a,
            role="farm_manager",
        )

        self.client.force_login(self.manager_a)
        url = reverse("remove_user", args=[manager_a2.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_delete_own_volunteer(self):
        self.client.force_login(self.manager_a)
        url = reverse("remove_user", args=[self.volunteer_a.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(id=self.volunteer_a.id).exists())