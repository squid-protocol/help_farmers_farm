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
        
        # THE FIX: Explicitly grant the Manager role here!
        self.manager_a = User.objects.create_user(
            username="manager_a", 
            password="secure", 
            farm=self.farm_a,
            role="farm_manager"  # <-- If this fails, check models.py; it might be lowercase "manager"
        )
        
        self.volunteer_a = User.objects.create_user(username="vol_a", password="secure", farm=self.farm_a)
        
        # 2. Build Farm B (The Rivals)
        self.farm_b = Farm.objects.create(name="Rival Valley Farms")
        self.volunteer_b = User.objects.create_user(username="vol_b", password="secure", farm=self.farm_b)

    def test_manager_can_view_own_volunteer(self):
        # Act: Manager A logs in and visits their own volunteer's page
        self.client.force_login(self.manager_a)
        
        url = reverse('volunteer_detail', args=[self.volunteer_a.id]) 
        response = self.client.get(url)
        
        # Assert: The server should allow it (HTTP 200 Success)
        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_view_rival_volunteer_idor(self):
        # Act: Manager A gets sneaky and tries to view Farm B's volunteer
        self.client.force_login(self.manager_a)
        
        url = reverse('volunteer_detail', args=[self.volunteer_b.id])
        response = self.client.get(url)
        
        # Assert: The server MUST block it. 
        self.assertEqual(response.status_code, 404)
        
    def test_manager_cannot_delete_rival_volunteer(self):
        # Act: Manager A tries to POST a delete request for Farm B's volunteer
        self.client.force_login(self.manager_a)
        
        # Note: Check your farms/urls.py to ensure the name is 'remove_user'
        url = reverse('remove_user', args=[self.volunteer_b.id])
        response = self.client.post(url)
        
        # Assert: The server MUST block it with a 403 Forbidden
        self.assertEqual(response.status_code, 403)
        # Verify the user was NOT actually deleted from the database
        self.assertTrue(User.objects.filter(id=self.volunteer_b.id).exists())

    def test_manager_cannot_delete_another_manager(self):
        # Arrange: Create a second manager in Farm A
        manager_a2 = User.objects.create_user(
            username="manager_a2", password="secure", 
            farm=self.farm_a, role="farm_manager"
        )
        
        # Act: Manager A tries to delete Manager A2
        self.client.force_login(self.manager_a)
        url = reverse('remove_user', args=[manager_a2.id])
        response = self.client.post(url)
        
        # Assert: Blocked by Rule #2 (Managers can't delete managers)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_delete_own_volunteer(self):
        # The Happy Path: Manager A deletes their own volunteer
        self.client.force_login(self.manager_a)
        url = reverse('remove_user', args=[self.volunteer_a.id])
        response = self.client.post(url)
        
        # Assert: It should work and redirect back to the dashboard
        self.assertEqual(response.status_code, 302)
        # The ultimate proof: The user should no longer exist in the database
        self.assertFalse(User.objects.filter(id=self.volunteer_a.id).exists())