from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from farms.models import Farm, ComplianceForm
from accounts.models import FormSignature

User = get_user_model()


class FarmModelTests(TestCase):
    def test_account_number_generation(self):
        """Ensure a unique system account number is generated on creation."""
        farm = Farm.objects.create(name="Auto Number Farm")
        self.assertIsNotNone(farm.account_number)
        self.assertTrue(farm.account_number.startswith("FARM-"))

    def test_trial_days_remaining(self):
        """Ensure the 60-day trial calculates correctly and doesn't go negative."""
        farm = Farm.objects.create(name="Trial Farm")

        # Fresh farm should have 60 days
        self.assertEqual(farm.trial_days_remaining, 60)

        # Fast forward 10 days
        farm.created_at = timezone.now() - timedelta(days=10)
        farm.save()
        self.assertEqual(farm.trial_days_remaining, 50)

        # Fast forward 70 days (expired)
        farm.created_at = timezone.now() - timedelta(days=70)
        farm.save()
        self.assertEqual(farm.trial_days_remaining, 0)

    def test_can_use_waivers_feature_flag(self):
        """Ensure the Compliance Engine is paywalled correctly."""
        # Starter tier
        starter_farm = Farm.objects.create(name="Starter Farm", subscription_tier="starter")
        self.assertFalse(starter_farm.can_use_waivers)

        # Growth tier
        growth_farm = Farm.objects.create(name="Growth Farm", subscription_tier="growth")
        self.assertTrue(growth_farm.can_use_waivers)

    def test_full_address_property(self):
        """Ensure the structured address fields combine properly for the mapping API."""
        farm = Farm.objects.create(
            name="Address Farm",
            address_line1="123 Farm Way",
            city="Alto",
            state="MI",
            postal_code="49302",
        )
        self.assertEqual(farm.full_address, "123 Farm Way, Alto, MI, 49302")


class ComplianceFormModelTests(TestCase):
    def setUp(self):
        self.farm = Farm.objects.create(name="Model Test Farm")
        self.user = User.objects.create_user(username="signer", email="signer@test.com")
        self.form = ComplianceForm.objects.create(farm=self.farm, name="Waiver v1", body_text="Do not sue us.")

    def test_is_currently_valid(self):
        """Ensure the compliance form correctly evaluates its expiration status."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # 1. Active, no expiration
        form1 = ComplianceForm(farm=self.farm, is_active=True)
        self.assertTrue(form1.is_currently_valid())

        # 2. Inactive
        form2 = ComplianceForm(farm=self.farm, is_active=False)
        self.assertFalse(form2.is_currently_valid())

        # 3. Expired yesterday
        form3 = ComplianceForm(farm=self.farm, is_active=True, does_expire=True, expiration_date=yesterday)
        self.assertFalse(form3.is_currently_valid())

        # 4. Expiring tomorrow
        form4 = ComplianceForm(farm=self.farm, is_active=True, does_expire=True, expiration_date=tomorrow)
        self.assertTrue(form4.is_currently_valid())

    def test_compliance_form_str(self):
        """Ensure the string representation formats correctly."""
        form = ComplianceForm.objects.create(farm=self.farm, name="2026 Waiver")
        self.assertEqual(str(form), "2026 Waiver - Model Test Farm")

    def test_unsigned_form_allows_text_alteration(self):
        """Ensure a manager can fix typos if no one has signed it yet."""
        self.form.body_text = "Updated Legal Text."
        self.form.save()  # Should succeed without raising an error

        self.form.refresh_from_db()
        self.assertEqual(self.form.body_text, "Updated Legal Text.")

    def test_signed_form_rejects_text_alteration(self):
        """Ensure a form physically locks its text once a signature is applied."""
        # 1. Apply a signature
        FormSignature.objects.create(user=self.user, form=self.form, digital_signature="John Doe")

        # 2. Attempt a malicious rewrite
        self.form.body_text = "You now owe the farm $1,000,000."

        # 3. Assert the ORM violently rejects the save
        with self.assertRaises(ValidationError) as context:
            self.form.save()

        self.assertIn("IMMUTABILITY LOCK", str(context.exception))

    def test_signed_form_allows_archiving(self):
        """Ensure a manager can still toggle is_active to archive a signed form."""
        FormSignature.objects.create(user=self.user, form=self.form, digital_signature="John Doe")

        # We are only changing the active status, NOT the text
        self.form.is_active = False
        self.form.save()  # Should succeed

        self.form.refresh_from_db()
        self.assertFalse(self.form.is_active)
