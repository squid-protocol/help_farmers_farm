from django.test import TestCase
from django.core import mail
from django.contrib.auth import get_user_model
from farms.models import Farm, WorkCommitment
from accounts.models import FarmMembership
from farms.tasks import send_volunteer_welcome_email, send_broadcast_email

User = get_user_model()


class EmailTaskTests(TestCase):
    def setUp(self):
        # 1. Build the World
        self.farm = Farm.objects.create(
            name="Testing Acres",
            welcome_email_subject="Welcome to Testing Acres!",
            welcome_email_body="We are so glad you are here.",
        )

        self.tier_heavy = WorkCommitment.objects.create(
            farm=self.farm, name="Heavy Lifting", required_hours=50
        )
        self.tier_light = WorkCommitment.objects.create(
            farm=self.farm, name="Light Weeding", required_hours=10
        )

        # 2. Build the Roster
        # User 1: Standard Volunteer
        self.vol_standard = User.objects.create_user(
            username="standard", email="standard@test.com", password="p"
        )
        FarmMembership.objects.create(
            user=self.vol_standard, farm=self.farm, is_approved=True
        )

        # User 2: Heavy Tier Volunteer
        self.vol_heavy = User.objects.create_user(
            username="heavy", email="heavy@test.com", password="p"
        )
        FarmMembership.objects.create(
            user=self.vol_heavy,
            farm=self.farm,
            is_approved=True,
            work_commitment=self.tier_heavy,
        )

        # User 3: Friend (Should NOT receive broadcasts)
        self.friend = User.objects.create_user(
            username="friend", email="friend@test.com", password="p", role="friend"
        )
        FarmMembership.objects.create(
            user=self.friend, farm=self.farm, is_approved=True
        )

        # User 4: Archived/Inactive User (Should NOT receive broadcasts)
        self.vol_inactive = User.objects.create_user(
            username="inactive",
            email="inactive@test.com",
            password="p",
            is_active=False,
        )
        FarmMembership.objects.create(
            user=self.vol_inactive, farm=self.farm, is_approved=True
        )

        # Clear the outbox just in case
        mail.outbox = []

    def test_send_volunteer_welcome_email(self):
        """Ensure the welcome email compiles and sends properly."""
        status = send_volunteer_welcome_email(
            user_id=self.vol_standard.id,
            farm_id=self.farm.id,
            raw_password="temp_password_123",
        )

        self.assertIn("Welcome email sent", status)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Welcome to Testing Acres!")
        self.assertEqual(mail.outbox[0].to, ["standard@test.com"])
        self.assertIn(
            "temp_password_123", mail.outbox[0].body
        )  # Prove password was injected

    def test_welcome_email_fails_gracefully_on_bad_data(self):
        """Ensure it doesn't crash the server if a bad ID is passed."""
        status = send_volunteer_welcome_email(
            user_id=9999, farm_id=self.farm.id, raw_password="p"
        )
        self.assertEqual(status, "Failed: User or Farm not found.")
        self.assertEqual(len(mail.outbox), 0)

    def test_broadcast_to_all_active_volunteers(self):
        """Ensure broadcasts go to active volunteers but ignore friends and inactive accounts."""
        status = send_broadcast_email(
            farm_id=self.farm.id,
            subject="Farm Update",
            custom_body="Big storm coming!",
            audience_value="all",
        )

        # Should only send to vol_standard and vol_heavy (2 people)
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
