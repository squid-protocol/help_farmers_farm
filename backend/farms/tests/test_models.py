from django.test import TestCase
from farms.models import Farm, ComplianceForm
from django.utils import timezone
from datetime import timedelta


class ComplianceFormModelTests(TestCase):
    def setUp(self):
        self.farm = Farm.objects.create(name="Model Test Farm")

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
        form3 = ComplianceForm(
            farm=self.farm, is_active=True, does_expire=True, expiration_date=yesterday
        )
        self.assertFalse(form3.is_currently_valid())

        # 4. Expiring tomorrow
        form4 = ComplianceForm(
            farm=self.farm, is_active=True, does_expire=True, expiration_date=tomorrow
        )
        self.assertTrue(form4.is_currently_valid())

    def test_compliance_form_str(self):
        """Ensure the string representation formats correctly."""
        form = ComplianceForm.objects.create(
            farm=self.farm, name="2026 Waiver", body_text="Test"
        )
        self.assertEqual(str(form), "2026 Waiver - Model Test Farm")

    def test_string_representations(self):
        """Covers lines 55, 94, 132: The __str__ methods for Farm, Crop, Commitment, and Form."""
        from farms.models import Crop, WorkCommitment

        self.assertEqual(str(self.farm), "Model Test Farm")

        crop1 = Crop.objects.create(farm=self.farm, crop_name="Corn", variety="Sweet")
        self.assertEqual(str(crop1), "Corn - Sweet")

        crop2 = Crop.objects.create(farm=self.farm, crop_name="Wheat")
        self.assertEqual(str(crop2), "Wheat")

        commitment = WorkCommitment.objects.create(
            farm=self.farm, name="Half Share", required_hours=40, symbol="🌓"
        )
        self.assertEqual(str(commitment), "🌓 Half Share (40 hrs)")

        form = ComplianceForm.objects.create(
            farm=self.farm, name="Waiver", body_text="text"
        )
        self.assertEqual(str(form), "Waiver - Model Test Farm")


class ComplianceFormImmutabilityTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        self.farm = Farm.objects.create(name="Secure Farm")
        self.form = ComplianceForm.objects.create(
            farm=self.farm, name="2026 Waiver", body_text="Original Legal Text."
        )
        self.user = User.objects.create_user(username="signer", password="p")

    def test_unsigned_form_can_be_edited(self):
        """Ensure a manager can fix typos if no one has signed it yet."""
        self.form.body_text = "Updated Legal Text."
        self.form.save()  # Should succeed without raising an error

        self.form.refresh_from_db()
        self.assertEqual(self.form.body_text, "Updated Legal Text.")

    def test_signed_form_rejects_text_alteration(self):
        """Ensure a form physically locks its text once a signature is applied."""
        from accounts.models import FormSignature
        from django.core.exceptions import ValidationError

        # 1. Apply a signature
        FormSignature.objects.create(
            user=self.user, form=self.form, digital_signature="John Doe"
        )

        # 2. Attempt a malicious rewrite
        self.form.body_text = "You now owe the farm $1,000,000."

        # 3. Assert the ORM violently rejects the save
        with self.assertRaises(ValidationError) as context:
            self.form.save()

        self.assertIn("IMMUTABILITY LOCK", str(context.exception))

    def test_signed_form_allows_archiving(self):
        """Ensure a manager can still toggle is_active to archive a signed form."""
        from accounts.models import FormSignature

        FormSignature.objects.create(
            user=self.user, form=self.form, digital_signature="John Doe"
        )

        # We are only changing the active status, NOT the text
        self.form.is_active = False
        self.form.save()  # Should succeed

        self.form.refresh_from_db()
        self.assertFalse(self.form.is_active)
