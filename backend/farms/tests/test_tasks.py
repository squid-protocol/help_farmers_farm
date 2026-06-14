from django.test import TestCase
from django.core import mail
from django.contrib.auth import get_user_model
from farms.models import Farm, WorkCommitment
from accounts.models import FarmMembership
from farms.tasks import send_volunteer_welcome_email, send_broadcast_email
from unittest.mock import patch, MagicMock
from geopy.exc import GeocoderTimedOut

User = get_user_model()


class EmailTaskTests(TestCase):
    def setUp(self):
        # 1. Build the World
        self.farm = Farm.objects.create(
            name="Testing Acres",
            welcome_email_subject="Welcome to Testing Acres!",
            welcome_email_body="<p>We are so <strong>glad</strong> you are here.</p>",
        )

        self.tier_heavy = WorkCommitment.objects.create(farm=self.farm, name="Heavy Lifting", required_hours=50)
        self.tier_light = WorkCommitment.objects.create(farm=self.farm, name="Light Weeding", required_hours=10)

        # 2. Build the Roster
        # User 1: Standard Volunteer (Active)
        self.vol_standard = User.objects.create_user(username="standard", email="standard@test.com", password="p")
        FarmMembership.objects.create(user=self.vol_standard, farm=self.farm, is_approved=True)

        # User 2: Heavy Tier Volunteer (Active)
        self.vol_heavy = User.objects.create_user(username="heavy", email="heavy@test.com", password="p")
        FarmMembership.objects.create(
            user=self.vol_heavy,
            farm=self.farm,
            is_approved=True,
            work_commitment=self.tier_heavy,
        )

        # User 3: Inactive User
        self.vol_inactive = User.objects.create_user(
            username="inactive",
            email="inactive@test.com",
            password="p",
            is_active=False,
        )
        FarmMembership.objects.create(user=self.vol_inactive, farm=self.farm, is_approved=True)

        # User 4: Legacy Friend
        self.vol_friend = User.objects.create_user(
            username="friend", email="friend@test.com", password="p", role="friend"
        )
        FarmMembership.objects.create(user=self.vol_friend, farm=self.farm, is_approved=True)

    def test_broadcast_to_all_active_volunteers_ignores_ghosts(self):
        """Ensure broadcasts skip inactive users and 'friend' roles."""
        status = send_broadcast_email(
            farm_id=self.farm.id,
            subject="Farm Update",
            custom_body="Here is the update.",
            audience_value="all",
        )

        self.assertIn("Broadcast sent to 2 recipients", status)
        self.assertEqual(len(mail.outbox), 2)

        # Verify emails were actually compiled correctly
        recipients = [email.to[0] for email in mail.outbox]
        self.assertIn("standard@test.com", recipients)
        self.assertIn("heavy@test.com", recipients)
        self.assertNotIn("friend@test.com", recipients)  # Prove the filter worked
        self.assertNotIn("inactive@test.com", recipients)

    def test_broadcast_to_specific_tier(self):
        """Ensure the targeting engine correctly isolates work commitments."""
        status = send_broadcast_email(
            farm_id=self.farm.id,
            subject="Heavy Lifters Only",
            custom_body="We need you.",
            audience_value=f"tier_{self.tier_heavy.id}",
        )

        self.assertIn("Broadcast sent to 1 recipients", status)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["heavy@test.com"])

    def test_broadcast_to_specific_users(self):
        """Ensure the manual checkbox targeting engine works securely."""
        status = send_broadcast_email(
            farm_id=self.farm.id,
            subject="You specifically",
            custom_body="Read this.",
            audience_value="specific",
            specific_ids=[str(self.vol_standard.id)],
        )

        self.assertIn("Broadcast sent to 1 recipients", status)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["standard@test.com"])

    def test_welcome_email_strips_html(self):
        """Ensure the plain-text alternative strips Trix HTML tags."""
        status = send_volunteer_welcome_email(
            user_id=self.vol_standard.id,
            farm_id=self.farm.id,
            raw_password="temp_password",
        )

        self.assertIn("Welcome email sent", status)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        # Check HTML part
        self.assertIn(
            "<p>We are so <strong>glad</strong> you are here.</p>",
            email.alternatives[0][0],
        )

        # Check Plain Text part
        self.assertNotIn("<strong>", email.body)
        self.assertNotIn("<p>", email.body)
        self.assertIn("We are so glad you are here.", email.body)


class GeocodingTaskTests(TestCase):
    def setUp(self):
        self.farm = Farm.objects.create(
            name="Map Farm",
            address_line1="123 Missing St",
            city="Nowhere",
            state="MI",
            postal_code="49000",
        )

    @patch("geopy.geocoders.Nominatim.geocode")
    def test_geocode_success_strict_address(self, mock_geocode):
        """Ensure a perfect address match saves the coordinates."""
        # Fake a successful OpenStreetMap response
        mock_location = MagicMock()
        mock_location.latitude = 42.0
        mock_location.longitude = -85.0
        mock_geocode.return_value = mock_location

        # Run the task manually
        from farms.tasks import geocode_farm_address

        geocode_farm_address(self.farm.id)

        self.farm.refresh_from_db()
        self.assertEqual(self.farm.latitude, 42.0)
        self.assertEqual(self.farm.longitude, -85.0)

    @patch("time.sleep", return_value=None)  # Skip the 1-second delay in tests
    @patch("geopy.geocoders.Nominatim.geocode")
    def test_geocode_fallback_mechanism(self, mock_geocode, mock_sleep):
        """Ensure it falls back to City/State if the strict street fails."""
        # Fake a failure on the first try, but success on the second (fallback)
        mock_location = MagicMock()
        mock_location.latitude = 43.0
        mock_location.longitude = -86.0

        # side_effect allows us to return different things on subsequent calls
        mock_geocode.side_effect = [None, mock_location]

        from farms.tasks import geocode_farm_address

        geocode_farm_address(self.farm.id)

        self.farm.refresh_from_db()
        self.assertEqual(self.farm.latitude, 43.0)
        self.assertEqual(mock_geocode.call_count, 2)  # Proves it tried the fallback!

    @patch("geopy.geocoders.Nominatim.geocode")
    def test_geocode_api_timeout_graceful_fail(self, mock_geocode):
        """Ensure the background worker doesn't crash if the API times out."""
        mock_geocode.side_effect = GeocoderTimedOut("Service unavailable")

        from farms.tasks import geocode_farm_address

        # This should execute and swallow the error, NOT raise an exception
        try:
            geocode_farm_address(self.farm.id)
            crashed = False
        except Exception:
            crashed = True

        self.assertFalse(crashed)
