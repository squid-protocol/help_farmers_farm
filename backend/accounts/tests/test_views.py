import requests
from decimal import Decimal  # <-- Missing Decimal
from django.db.models import Sum
from django.utils import timezone
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from farms.models import Farm, ComplianceForm
from accounts.models import FarmMembership, FormSignature
from django.core import mail
from django.core.signing import TimestampSigner
from unittest.mock import patch
from django.contrib.auth import authenticate
from logs.models import LogEntry

User = get_user_model()


class LoginActionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Schuler Test Farm")

        self.user = User.objects.create_user(
            username="test_volunteer",
            email="test_vol@example.com",
            password="my_secure_password123",
        )
        FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True, agreed_to_waiver=True
        )
        self.login_url = reverse("login")

    def test_successful_login_redirects(self):
        response = self.client.post(
            self.login_url,
            {"username": "test_volunteer", "password": "my_secure_password123"},
        )
        self.assertRedirects(response, "/log-hours/", target_status_code=200)

    def test_failed_login_shows_error(self):
        response = self.client.post(
            self.login_url, {"username": "test_volunteer", "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your username and password didn't match")


class ProfileViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Test Farm")

        self.user = User.objects.create_user(
            username="profile_tester",
            email="profile_tester@example.com",
            password="testpass123",
            address_line1="123 Test Lane",
            city="Farmingville",
            state="MI",
            postal_code="48103",
        )
        FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True, agreed_to_waiver=True
        )
        self.client.force_login(self.user)

    def test_profile_view_get(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_view_post_valid(self):
        post_data = {
            "username": self.user.username,
            "first_name": "Updated",
            "last_name": "Name",
            "email": "test@example.com",
            "phone_number": "+12025550150",
            "address_line1": "123 Test Lane",
            "city": "Farmingville",
            "state": "MI",
            "postal_code": "48103",
        }
        response = self.client.post(reverse("profile"), post_data)
        self.assertRedirects(response, reverse("profile"))

    def test_upload_avatar_post(self):
        dummy_base64_image = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
            "HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        response = self.client.post(
            reverse("upload_avatar"), {"avatar_base64": dummy_base64_image}
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))

    def test_upload_avatar_post_empty(self):
        """Covers lines 61-64: Missing base64 data."""
        response = self.client.post(reverse("upload_avatar"), {})
        self.assertRedirects(response, reverse("profile"))

    def test_upload_avatar_blocks_xss_file_extension(self):
        """Ensure the backend hardcodes .jpg and ignores forged HTML MIME types."""
        malicious_base64 = "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="
        response = self.client.post(
            reverse("upload_avatar"), {"avatar_base64": malicious_base64}
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))
        self.assertTrue(self.user.avatar.name.endswith(".jpg"))
        self.assertFalse(self.user.avatar.name.endswith(".html"))

    def test_profile_view_rejects_invalid_phone(self):
        """Ensure the profile form strictly validates phone numbers."""
        post_data = {
            "username": self.user.username,
            "first_name": "Updated",
            "last_name": "Name",
            "email": "test@example.com",
            "phone_number": "Not a real number",
            "address_line1": "123 Test Lane",
            "city": "Farmingville",
            "state": "MI",
            "postal_code": "48103",
        }
        response = self.client.post(reverse("profile"), post_data)

        # It should bounce back to the form (200), not redirect (302)
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone_number", response.context["form"].errors)

    def test_profile_view_displays_signed_documents(self):
        """Phase 3: Ensure signed documents are passed to the profile context."""
        from farms.models import ComplianceForm
        from accounts.models import FormSignature

        # Give them a signed form
        form = ComplianceForm.objects.create(
            farm=self.farm, name="Test Doc", body_text="text"
        )
        FormSignature.objects.create(
            user=self.user, form=form, digital_signature="Test Name"
        )

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("signatures", response.context)
        self.assertEqual(response.context["signatures"].count(), 1)

    def test_profile_zero_hours_state(self):
        """Edge Case: The profile should render the 'Zero State' dummy charts if hours are 0."""
        # Ensure the user has absolutely no logs
        LogEntry.objects.filter(volunteer=self.user).delete()

        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        # Should render the fallback gray chart for Onions, Lettuce, Carrots, etc.
        self.assertIn("0 Hours Logged", str(response.content))

    def test_waiver_guardian_missing_relationship(self):
        """Unhappy Path: Guardian checks the box but leaves relationship blank."""
        self.client.force_login(self.user)

        # Bypass the profile completeness check and email verification check
        self.user.first_name = "John"
        self.user.last_name = "Doe"
        self.user.phone_number = "+15551234567"
        self.user.address_line1 = "123 Street"
        self.user.city = "City"
        self.user.state = "MI"
        self.user.postal_code = "12345"
        self.user.is_email_verified = True
        self.user.save()

        form_to_sign = ComplianceForm.objects.create(
            farm=self.farm, name="Test Form", is_active=True
        )

        response = self.client.post(
            reverse("sign_waiver"),
            {
                "sign_document": "true",
                "form_id": form_to_sign.id,
                "digital_signature": "John Doe",
                "is_guardian": "on",
                "guardian_relationship": "",  # Left blank!
            },
        )

        # Should fail and return the error message
        messages = list(response.context["messages"])
        self.assertTrue(any("relationship to the minor" in str(m) for m in messages))

    def test_waiver_signature_name_mismatch(self):
        """Unhappy Path: Signature does not match the user's name or username."""
        self.client.force_login(self.user)

        # Bypass the profile completeness check and email verification check
        self.user.first_name = "Joe"
        self.user.last_name = "Farmer"
        self.user.phone_number = "+15551234567"
        self.user.address_line1 = "123 Street"
        self.user.city = "City"
        self.user.state = "MI"
        self.user.postal_code = "12345"
        self.user.is_email_verified = True
        self.user.save()

        form_to_sign = ComplianceForm.objects.create(
            farm=self.farm, name="Test Form", is_active=True
        )

        response = self.client.post(
            reverse("sign_waiver"),
            {
                "sign_document": "true",
                "form_id": form_to_sign.id,
                "digital_signature": "Jane Doe",  # Wrong name!
            },
        )

        messages = list(response.context["messages"])
        self.assertTrue(
            any("match your first and last name" in str(m) for m in messages)
        )

    def test_verify_email_wrong_user_token(self):
        """Security: User clicks an email verification link meant for someone else."""
        other_user = User.objects.create_user(username="other", password="p")

        # Generate a valid token, but for 'other_user'
        from django.core.signing import TimestampSigner

        token = TimestampSigner().sign(other_user.id)

        # Login as self.user
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("verify_email_link", args=[token]), follow=True
        )

        # Should fail security check
        messages = list(response.context["messages"])
        self.assertTrue(
            any("belongs to a different account" in str(m) for m in messages)
        )
        self.assertFalse(self.user.is_email_verified)

    def test_verify_email_invalid_token(self):
        """Unhappy Path: User clicks a corrupted or expired email link."""
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("verify_email_link", args=["garbage:token:123"]), follow=True
        )

        messages = list(response.context["messages"])
        self.assertTrue(any("invalid or has expired" in str(m) for m in messages))


class LegacyClaimFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Legacy Farm")

        self.ghost_user = User.objects.create(
            username="john_doe", first_name="John", last_name="Doe", email=""
        )
        self.ghost_user.set_unusable_password()
        self.ghost_user.save()

        self.claimed_user = User.objects.create_user(
            username="jane_doe",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            password="securepassword",
        )
        self.search_url = reverse("claim_search")
        self.setup_url = reverse("claim_setup", args=[self.ghost_user.id])

    def test_search_finds_unclaimed_account(self):
        response = self.client.post(self.search_url, {"search_name": "John"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.ghost_user, response.context["matches"])

    def test_search_fails_gracefully_on_no_match(self):
        response = self.client.post(self.search_url, {"search_name": "Ghostbuster"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["matches"])

    def test_setup_secures_account_and_logs_in(self):
        response = self.client.post(
            self.setup_url,
            {
                "email": "john.doe@newemail.com",
                "password": "newsecurepassword123",
                "confirm_password": "newsecurepassword123",
            },
        )
        self.assertRedirects(
            response, reverse("log_hours"), fetch_redirect_response=False
        )
        self.ghost_user.refresh_from_db()
        self.assertEqual(self.ghost_user.email, "john.doe@newemail.com")
        self.assertTrue(self.ghost_user.has_usable_password())

    def test_setup_rejects_mismatched_passwords(self):
        """Ensures the AccountClaimForm catches mismatched passwords."""
        response = self.client.post(
            self.setup_url,
            {
                "email": "john.doe@newemail.com",
                "password": "securepassword123",
                "confirm_password": "differentpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match.")

    def test_claim_account_setup_get(self):
        """Covers line 140: GET request for claim setup."""
        response = self.client.get(self.setup_url)
        self.assertEqual(response.status_code, 200)


class EmailTollboothTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Tollbooth Farm")
        self.no_email_user = User.objects.create_user(
            username="no_email_guy", email="", password="securepassword"
        )
        FarmMembership.objects.create(
            user=self.no_email_user, farm=self.farm, is_approved=True
        )
        self.update_url = reverse("update_email")

    def test_tollbooth_forces_redirect_for_missing_email(self):
        self.client.force_login(self.no_email_user)
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, self.update_url)

    def test_successful_email_update_clears_tollbooth(self):
        self.client.force_login(self.no_email_user)
        response = self.client.post(
            self.update_url, {"email": "nowihaveanemail@example.com"}
        )
        self.assertRedirects(response, "/")
        self.no_email_user.refresh_from_db()
        self.assertEqual(self.no_email_user.email, "nowihaveanemail@example.com")

    def test_email_middleware_allows_static_assets(self):
        self.client.force_login(self.no_email_user)
        from django.conf import settings

        response = self.client.get(f"{settings.STATIC_URL}css/dist/styles.css")
        self.assertNotEqual(response.status_code, 302)

    def test_email_tollbooth_allows_logout(self):
        """Ensure users trapped by the email tollbooth can still log out."""
        self.client.force_login(self.no_email_user)
        response = self.client.post(reverse("logout"))
        if hasattr(response, "url"):
            self.assertNotEqual(response.url, reverse("update_email"))

    def test_update_email_post_empty(self):
        """Covers line 84: Empty email submitted."""
        self.client.force_login(self.no_email_user)
        response = self.client.post(self.update_url, {"email": "   "})
        self.assertEqual(response.status_code, 200)


class ComplianceGateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Strict Liability Farm",
            welcome_email_body="Welcome!",
            welcome_email_subject="Hi!",
            subscription_tier="growth",
        )

        self.compliance_form = ComplianceForm.objects.create(
            farm=self.farm,
            name="2026 Safety Waiver",
            body_text="You must sign this to enter.",
            is_active=True,
            assignment_type="all",
        )

        self.user = User.objects.create_user(
            username="test_volunteer",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="securepassword",
            phone_number="+15555555555",
            address_line1="123 Farm Way",
            city="Farmingville",
            state="MI",
            postal_code="48103",
            is_email_verified=True,
        )
        self.membership = FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True
        )

        session = self.client.session
        session["active_farm_id"] = self.farm.id
        session.save()

        self.client.force_login(self.user)

    def test_middleware_redirects_to_waiver(self):
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_successful_signature_unlocks_account(self):
        response = self.client.post(
            reverse("sign_waiver"), {"signature": "John Doe", "sign_document": "true"}
        )
        self.assertRedirects(response, reverse("log_hours"))

        signature_exists = FormSignature.objects.filter(
            user=self.user, form=self.compliance_form
        ).exists()
        self.assertTrue(signature_exists)

    def test_waiver_get_request_renders_form(self):
        response = self.client.get(reverse("sign_waiver"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/sign_waiver.html")

    def test_waiver_rejects_wrong_name(self):
        response = self.client.post(
            reverse("sign_waiver"), {"signature": "Wrong Name", "sign_document": "true"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Your signature must match your first and last name exactly."
        )
        signature_exists = FormSignature.objects.filter(user=self.user).exists()
        self.assertFalse(signature_exists)

    def test_waiver_middleware_allows_static_assets(self):
        from django.conf import settings

        response = self.client.get(f"{settings.STATIC_URL}css/dist/styles.css")
        self.assertNotEqual(response.status_code, 302)

    def test_waiver_redirects_if_none_pending(self):
        FormSignature.objects.create(
            user=self.user, form=self.compliance_form, digital_signature="John Doe"
        )
        response = self.client.get(reverse("sign_waiver"))
        self.assertRedirects(response, reverse("log_hours"))

    def test_waiver_handles_multiple_forms(self):
        ComplianceForm.objects.create(
            farm=self.farm,
            name="Second Form",
            body_text="Another one",
            is_active=True,
            assignment_type="all",
        )
        response = self.client.post(
            reverse("sign_waiver"), {"signature": "John Doe", "sign_document": "true"}
        )
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_specific_assignment_waiver_logic(self):
        self.compliance_form.assignment_type = "specific"
        self.compliance_form.save()

        response = self.client.get(reverse("log_hours"))
        self.assertEqual(response.status_code, 200)

        self.compliance_form.assigned_users.add(self.user)
        response = self.client.get(reverse("log_hours"))
        self.assertRedirects(response, reverse("sign_waiver"))

    def test_starter_tier_bypasses_waiver(self):
        """Ensure volunteers on Starter tier farms are not blocked by the compliance gate."""
        self.farm.subscription_tier = "starter"
        self.farm.save()

        response = self.client.get(reverse("log_hours"))

        # Should be a clean 200 OK, not a 302 redirect to the sign_waiver page
        self.assertEqual(response.status_code, 200)

    def test_waiver_middleware_allows_logout(self):
        """Ensure users trapped by the waiver can still log out."""
        response = self.client.post(reverse("logout"))
        if hasattr(response, "url"):
            self.assertNotEqual(response.url, reverse("sign_waiver"))

    def test_waiver_accepts_guardian_signature(self):
        """Phase 2: Ensure a parent can sign for a minor without matching the account name."""
        response = self.client.post(
            reverse("sign_waiver"),
            {
                "is_guardian": "on",
                "guardian_relationship": "Mother",
                "signature": "Jane Doe",
                "sign_document": "true",
            },
        )
        # Should succeed and unlock the app
        self.assertRedirects(response, reverse("log_hours"))

        # Verify the database caught the guardian metadata
        sig = FormSignature.objects.get(user=self.user, form=self.compliance_form)
        self.assertTrue(sig.is_guardian_signature)
        self.assertEqual(sig.guardian_relationship, "Mother")
        self.assertEqual(sig.digital_signature, "Jane Doe")

    def test_waiver_rejects_guardian_without_relationship(self):
        """Phase 2: Ensure we mandate the relationship field for guardians."""
        response = self.client.post(
            reverse("sign_waiver"),
            {
                "is_guardian": "on",
                "guardian_relationship": "",  # Missing!
                "signature": "Jane Doe",
                "sign_document": "true",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please specify your relationship")

    def test_waiver_hard_blocks_incomplete_profile(self):
        """Ensure missing physical address redirects to profile."""
        self.user.address_line1 = ""
        self.user.save()
        response = self.client.get(reverse("sign_waiver"))
        self.assertRedirects(response, reverse("profile"))

    def test_waiver_hard_blocks_unverified_email_post(self):
        """Ensure unverified users cannot post a signature."""
        self.user.is_email_verified = False
        self.user.save()
        response = self.client.post(
            reverse("sign_waiver"), {"signature": "John Doe", "sign_document": "true"}
        )

        # It should bounce them back to the waiver page with the error message
        self.assertRedirects(response, reverse("sign_waiver"))

        # Verify the database physically rejected the signature creation
        signature_exists = FormSignature.objects.filter(
            user=self.user, form=self.compliance_form
        ).exists()
        self.assertFalse(signature_exists)


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Strict Liability Farm",
            welcome_email_body="Welcome!",
            welcome_email_subject="Hi!",
        )

        self.compliance_form = ComplianceForm.objects.create(
            farm=self.farm,
            name="2026 Safety Waiver",
            body_text="You must sign this to enter.",
            is_active=True,
            assignment_type="all",
        )

        self.user = User.objects.create_user(
            username="test_volunteer",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="securepassword",
            phone_number="+15555555555",
            address_line1="123 Farm Way",
            city="Farmingville",
            state="MI",
            postal_code="48103",
            is_email_verified=False,
        )
        self.user.is_email_verified = False
        self.user.save()

        self.membership = FarmMembership.objects.create(
            user=self.user, farm=self.farm, is_approved=True
        )

        session = self.client.session
        session["active_farm_id"] = self.farm.id
        session.save()

        self.client.force_login(self.user)

    def test_send_verification_email(self):
        """Ensure the view generates a token and sends an email."""
        response = self.client.post(
            reverse("sign_waiver"), {"send_verification": "true"}
        )
        self.assertRedirects(response, reverse("sign_waiver"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify your signature account", mail.outbox[0].subject)

    def test_verify_email_link_valid(self):
        """Ensure a valid cryptographic token flips the verification boolean."""
        signer = TimestampSigner()
        token = signer.sign(self.user.id)
        response = self.client.get(reverse("verify_email_link", args=[token]))

        self.assertRedirects(response, reverse("sign_waiver"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_verify_email_link_wrong_user(self):
        """Ensure a user cannot use someone else's token to verify their own account."""
        signer = TimestampSigner()
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password="p"
        )
        token = signer.sign(other_user.id)

        self.client.get(reverse("verify_email_link", args=[token]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_verify_email_link_invalid_token(self):
        """Ensure tampered or expired tokens fail securely."""
        self.client.get(reverse("verify_email_link", args=["tampered:token:here"]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_signature_with_x_forwarded_for(self):
        """Ensure the server correctly extracts the real IP address behind a proxy."""
        self.user.is_email_verified = True
        self.user.save()

        self.client.post(
            reverse("sign_waiver"),
            {"signature": "John Doe", "sign_document": "true"},
            HTTP_X_FORWARDED_FOR="192.168.1.1, 10.0.0.1",
        )
        sig = FormSignature.objects.first()
        self.assertEqual(sig.signer_ip_address, "192.168.1.1")

    def test_signature_prioritizes_cloudflare_ip(self):
        """Ensure Cloudflare's secure header overrides the easily spoofable X-Forwarded-For."""
        self.user.is_email_verified = True
        self.user.save()

        self.client.post(
            reverse("sign_waiver"),
            {"signature": "John Doe", "sign_document": "true"},
            HTTP_CF_CONNECTING_IP="203.0.113.1",
            HTTP_X_FORWARDED_FOR="192.168.1.1, 10.0.0.1",  # Spoofed payload
        )
        sig = FormSignature.objects.first()
        # Should ignore the 192.168.1.1 and grab the Cloudflare header
        self.assertEqual(sig.signer_ip_address, "203.0.113.1")

    def test_form_signature_str_methods(self):
        """Ensure the string representations for the WORM database audit logs format correctly."""
        self.user.is_email_verified = True
        self.user.save()

        # Test Standard Signature
        sig1 = FormSignature.objects.create(
            user=self.user, form=self.compliance_form, digital_signature="John Doe"
        )
        self.assertEqual(
            str(sig1), f"test_volunteer signed {self.compliance_form.name}"
        )

        # Test Guardian Signature (Use a second form to avoid the unique DB constraint)
        form2 = ComplianceForm.objects.create(
            farm=self.farm, name="Minor Safety Addendum", body_text="text"
        )
        sig2 = FormSignature.objects.create(
            user=self.user,
            form=form2,
            digital_signature="Jane Doe",
            is_guardian_signature=True,
            guardian_relationship="Mother",
        )
        self.assertEqual(
            str(sig2), f"Jane Doe (Guardian) signed {form2.name} for test_volunteer"
        )


class SignatureEvasionTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Build the target farm and form
        self.farm_a = Farm.objects.create(
            name="Authorized Farm", subscription_tier="growth"
        )
        self.form_a = ComplianceForm.objects.create(
            farm=self.farm_a,
            name="2026 Liability Waiver",
            body_text="I agree to not sue.",
            is_active=True,
        )

        # 2. Build a rival farm and form to test cross-tenant pollution
        self.farm_b = Farm.objects.create(name="Rival Farm", subscription_tier="growth")
        self.form_b = ComplianceForm.objects.create(
            farm=self.farm_b,
            name="Rival Liability Waiver",
            body_text="I agree to not sue the rival.",
            is_active=True,
        )

        # 3. Create our volunteer and link them ONLY to Farm A
        # FIX: We must give them a full profile and verify their email,
        # otherwise your security tollbooths will kick them out with a 302!
        self.volunteer = User.objects.create_user(
            username="sneaky_vol",
            email="sneak@test.com",
            password="p",
            first_name="John",
            last_name="Doe",
            phone_number="(555) 123-4567",
            address_line1="123 Farm Lane",
            city="Farmingville",
            state="MI",
            postal_code="48103",
            is_email_verified=True,
        )

        FarmMembership.objects.create(
            user=self.volunteer, farm=self.farm_a, is_approved=True
        )

        self.client.force_login(self.volunteer)

        # The URL does NOT take an ID in the route based on accounts/urls.py
        self.sign_url = reverse("sign_waiver")

    def test_blank_signature_rejected_gracefully(self):
        """Ensure an empty signature string fails backend form validation."""
        response = self.client.post(
            self.sign_url,
            {
                "form_id": self.form_a.id,
                "digital_signature": "",
                "agree_to_terms": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        # Check that the view generated an error message
        messages = list(response.context["messages"])
        self.assertTrue(any("required" in str(m.message) for m in messages))
        self.assertEqual(FormSignature.objects.count(), 0)

    def test_whitespace_only_signature_rejected(self):
        """Ensure users cannot bypass the requirement by just typing spaces."""
        response = self.client.post(
            self.sign_url,
            {
                "form_id": self.form_a.id,
                "digital_signature": "    ",
                "agree_to_terms": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("required" in str(m.message) for m in messages))
        self.assertEqual(FormSignature.objects.count(), 0)

    def test_cannot_sign_rival_farm_waiver_idor(self):
        """Ensure a user cannot submit a signature for a form belonging to a farm they aren't in."""
        response = self.client.post(
            self.sign_url,
            {
                "form_id": self.form_b.id,
                "digital_signature": "John Doe",
                "agree_to_terms": True,
            },
        )

        # The new PermissionDenied exception will trigger a 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertEqual(FormSignature.objects.filter(form=self.form_b).count(), 0)


class AccountDeletionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Test Farm")
        self.user = User.objects.create_user(
            username="delete_me",
            first_name="John",
            last_name="Doe",
            email="john@test.com",
            phone_number="+15555555555",
            password="securepassword",
        )
        self.client.force_login(self.user)

    def test_delete_account_triggers_anonymization(self):
        """Ensure the CCPA/GDPR protocol strips identity but keeps the DB shell."""
        response = self.client.post(reverse("delete_account"))

        # User should be redirected home and logged out
        self.assertRedirects(response, reverse("home"))

        # Pull the user back from the DB and verify destruction
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.first_name, "Anonymous")
        self.assertEqual(self.user.last_name, "Volunteer")
        self.assertIn("redacted_", self.user.email)
        self.assertIn("deleted.local", self.user.email)
        self.assertEqual(self.user.role, "friend")
        self.assertFalse(self.user.has_usable_password())


class RegistrationSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.vol_url = "/accounts/signup/volunteer/"
        self.farm_url = "/accounts/signup/farm/"

    def test_honeypot_trap_volunteer(self):
        """Ensure bots filling out the hidden website_url field are dropped silently."""
        response = self.client.post(
            self.vol_url, {"website_url": "[http://spam.com](http://spam.com)"}
        )
        self.assertRedirects(response, "/")
        self.assertEqual(User.objects.count(), 0)

    def test_honeypot_trap_farm(self):
        """Ensure farm registration honeypot works."""
        response = self.client.post(
            self.farm_url, {"website_url": "[http://spam.com](http://spam.com)"}
        )
        self.assertRedirects(response, "/")
        self.assertEqual(Farm.objects.count(), 0)

    def test_missing_turnstile_token_fails(self):
        """Ensure submitting without JS/Turnstile fails the security check."""
        response = self.client.post(self.vol_url, {"cf-turnstile-response": ""})
        self.assertEqual(response.status_code, 200)
        msgs = list(response.context["messages"])
        self.assertTrue(any("Security check failed" in str(m.message) for m in msgs))

    @patch("accounts.views.requests.post")
    def test_turnstile_api_timeout_fails_securely(self, mock_post):
        """Ensure a Cloudflare API outage defaults to failing the registration."""
        mock_post.side_effect = requests.RequestException("Timeout")
        response = self.client.post(
            self.vol_url, {"cf-turnstile-response": "valid_token"}
        )
        self.assertEqual(response.status_code, 200)
        msgs = list(response.context["messages"])
        self.assertTrue(any("Security check failed" in str(m.message) for m in msgs))

    @patch("accounts.views.VolunteerSignUpForm")
    @patch("accounts.views.verify_turnstile", return_value=True)
    def test_volunteer_signup_success(self, mock_turnstile, MockFormClass):
        """Ensure volunteer registration assigns the correct role and logs them in."""
        mock_form = MockFormClass.return_value
        mock_form.is_valid.return_value = True

        mock_user = User(username="new_vol", email="vol@test.com")
        mock_user.backend = "django.contrib.auth.backends.ModelBackend"
        mock_form.save.return_value = mock_user

        response = self.client.post(self.vol_url, {"dummy": "data"})

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        db_user = User.objects.get(username="new_vol")
        self.assertEqual(db_user.role, "volunteer")

    @patch("accounts.views.FarmSignUpForm")
    @patch("accounts.views.verify_turnstile", return_value=True)
    def test_farm_atomic_provisioning_success(self, mock_turnstile, MockFormClass):
        """Ensure the Happy Path creates all three DB objects cleanly."""
        mock_form = MockFormClass.return_value
        mock_form.is_valid.return_value = True
        mock_form.cleaned_data = {
            "farm_name": "Atomic Farm",
            "farm_phone": "(555) 123-4567",
        }

        # Form.save(commit=False) normally returns a new unsaved user object
        mock_user = User(username="atomic_manager", email="atomic@example.com")
        mock_user.backend = "django.contrib.auth.backends.ModelBackend"
        mock_form.save.return_value = mock_user

        response = self.client.post(self.farm_url, {"dummy": "data"})

        # View redirects to manager_dashboard on success
        self.assertRedirects(
            response, reverse("manager_dashboard"), fetch_redirect_response=False
        )

        # Verify DB state
        self.assertTrue(User.objects.filter(username="atomic_manager").exists())
        self.assertTrue(Farm.objects.filter(name="Atomic Farm").exists())

        # Ensure the user was elevated to a farm_manager
        db_user = User.objects.get(username="atomic_manager")
        self.assertEqual(db_user.role, "farm_manager")
        self.assertTrue(
            FarmMembership.objects.filter(user=db_user, is_approved=True).exists()
        )

    @patch("accounts.views.FarmMembership.objects.create")
    @patch("accounts.views.FarmSignUpForm")
    @patch("accounts.views.verify_turnstile", return_value=True)
    def test_farm_atomic_provisioning_rollback(
        self, mock_turnstile, MockFormClass, mock_membership_create
    ):
        """Ensure a failure mid-provisioning rolls back the ENTIRE transaction."""
        mock_form = MockFormClass.return_value
        mock_form.is_valid.return_value = True
        mock_form.cleaned_data = {
            "farm_name": "Rollback Farm",
            "farm_phone": "(555) 000-0000",
        }

        # Simulate the user being saved to the database during the transaction
        def fake_save(*args, **kwargs):
            user = User(username="rollback_target", email="rollback@example.com")
            user.save()
            return user

        mock_form.save.side_effect = fake_save

        # Force the 3rd step (Membership) to crash the transaction
        mock_membership_create.side_effect = Exception("Critical DB Failure")

        response = self.client.post(self.farm_url, {"dummy": "data"})

        # It should catch the exception and rerender the form
        self.assertEqual(response.status_code, 200)
        msgs = list(response.context["messages"])
        self.assertTrue(
            any("critical error setting up your account" in str(m.message) for m in msgs)
        )

        # CRITICAL ATOMIC CHECK: Neither the user nor the farm should exist in the DB!
        self.assertFalse(User.objects.filter(username="rollback_target").exists())
        self.assertFalse(Farm.objects.filter(name="Rollback Farm").exists())

    @patch("farms.models.Farm.objects.create")
    @patch("accounts.views.verify_turnstile", return_value=True)
    def test_farm_creation_failure_rolls_back_user(
        self, mock_turnstile, mock_farm_create
    ):
        """STABILITY: Ensure a database failure during registration doesn't leave orphaned users."""
        # Force the database to crash when trying to create the Farm
        mock_farm_create.side_effect = Exception("Database Outage Simulation")

        response = self.client.post(
            reverse("signup_farm"),
            {
                "farm_name": "Rollback Farm",
                "farm_phone": "(201) 555-0199",
                "username": "unlucky_manager",
                "first_name": "Unlucky",
                "last_name": "Guy",
                "email": "unlucky@test.com",
                "phone_number": "(201) 555-0100",
                "address_line1": "123 Fail St",
                "city": "Failville",
                "state": "MI",
                "postal_code": "48103",
                "password1": "securepassword123",
                "password2": "securepassword123",
            },
        )

        # It should catch the error and re-render the form
        self.assertEqual(response.status_code, 200)
        self.assertIn("There was a critical error", str(response.content))

        # CRITICAL: The user 'unlucky_manager' must NOT exist in the database
        self.assertFalse(User.objects.filter(username="unlucky_manager").exists())

    def test_honeypot_blocks_bot_registration(self):
        """SECURITY: Ensure bots that fill out the hidden website_url field are silently rejected."""
        response = self.client.post(
            reverse("signup_volunteer"),
            {
                "first_name": "Bad",
                "last_name": "Bot",
                "email": "bot@spam.com",
                "phone_number": "(555) 555-5555",
                "password": "securepassword123",
                "website_url": "http://spambot.com",  # <-- THE TRAP
            },
        )

        # It should pretend everything went fine and bounce them to the home page
        self.assertRedirects(response, reverse("home"))

        # CRITICAL: The user must NOT exist in the database
        self.assertFalse(User.objects.filter(email="bot@spam.com").exists())


class AvatarUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Ensure we have a valid logged-in user to test with
        self.user = User.objects.create_user(
            username="avatar_user", email="avatar@test.com", password="password123"
        )

    def test_avatar_upload_handles_missing_data(self):
        """Unhappy Path: Submit the avatar form with an empty payload."""
        self.client.force_login(self.user)
        response = self.client.post(reverse("upload_avatar"), {"avatar_base64": ""})

        # Should redirect back to profile without crashing
        self.assertRedirects(response, reverse("profile"))

        # Verify the error message was attached
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("No image data was received" in str(m) for m in messages))

    def test_avatar_upload_handles_corrupted_base64(self):
        """Unhappy Path: Submit garbage data that cannot be decoded."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("upload_avatar"),
            {"avatar_base64": "data:image/png;base64,NOT_A_REAL_IMAGE!@#$"},
        )

        self.assertRedirects(response, reverse("profile"))
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("error updating your avatar" in str(m) for m in messages))


class CustomAuthenticationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()  # <-- NEW: Simulate HTTP Requests
        self.user = User.objects.create_user(
            username="real_user", email="real@test.com", password="correct_password"
        )

    def test_auth_backend_rejects_unknown_user(self):
        """Unhappy Path: Logging in with an email that doesn't exist."""
        request = self.factory.get("/login/")
        user = authenticate(
            request=request, username="nobody@test.com", password="password"
        )
        self.assertIsNone(user)

    def test_auth_backend_rejects_bad_password(self):
        """Unhappy Path: Valid email, wrong password."""
        request = self.factory.get("/login/")
        user = authenticate(
            request=request, username="real@test.com", password="wrong_password"
        )
        self.assertIsNone(user)

    def test_auth_backend_accepts_valid_email(self):
        """Happy Path: Ensure the custom backend actually works for emails."""
        request = self.factory.get("/login/")
        user = authenticate(
            request=request, username="real@test.com", password="correct_password"
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "real_user")


class AccountSecurityIntegrityTests(TestCase):
    def setUp(self):
        self.farm = Farm.objects.create(name="Privacy Test Farm")
        self.user = User.objects.create_user(
            username="sensitive_user",
            email="private@test.com",
            first_name="Joseph",
            last_name="Esquibel",
            address_line1="8171 Country Pine Dr",
            city="Alto",
            state="MI",
            postal_code="49302",
            password="password123",
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        # Log a shift so we can prove it survives the deletion
        from logs.models import LogEntry

        LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            duration_hours=5.0,
            date_logged="2026-05-20",
            activity="P",
        )

    def test_account_anonymization_scrubs_pii_but_preserves_logs(self):
        """SECURITY: Verify that PII is destroyed while relational data remains for farm analytics."""
        self.client.force_login(self.user)

        # Trigger the anonymization protocol via the POST view
        response = self.client.post(reverse("delete_account"))

        self.assertRedirects(response, reverse("home"))

        # Refresh user from database
        self.user.refresh_from_db()

        # Verify PII is gone
        self.assertEqual(self.user.first_name, "Anonymous")
        self.assertEqual(self.user.last_name, "Volunteer")
        self.assertIn("redacted", self.user.email)
        self.assertEqual(self.user.address_line1, "Redacted per privacy request")
        self.assertEqual(self.user.postal_code, "00000")
        self.assertFalse(self.user.is_active)

        # Verify the Log remains in the database (SET_NULL)
        from logs.models import LogEntry

        log = LogEntry.objects.get(farm=self.farm)
        self.assertEqual(log.duration_hours, 5.0)
        self.assertEqual(log.volunteer, self.user)


class AccountAnonymizationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Security Audit Farm")

        self.user = User.objects.create_user(
            username="joseph_e",
            email="private_data@example.com",
            first_name="Joseph",
            last_name="Esquibel",
            address_line1="8171 Country Pine Dr",
            city="Alto",
            state="MI",
            postal_code="49302",
            phone_number="+15551234567",
            password="secure-password-123",
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)

        # LogEntry is now correctly imported and available here
        self.log_entry = LogEntry.objects.create(
            farm=self.farm,
            volunteer=self.user,
            duration_hours=Decimal("4.50"),
            date_logged=timezone.now().date(),
            activity="H",
        )

    def test_delete_account_view_scrubs_pii_correctly(self):
        """SECURITY: Verify that the anonymization protocol destroys PII but preserves analytics."""
        self.client.force_login(self.user)
        response = self.client.post(reverse("delete_account"))

        self.assertRedirects(response, reverse("home"))
        self.user.refresh_from_db()

        self.assertEqual(self.user.first_name, "Anonymous")
        self.assertEqual(self.user.last_name, "Volunteer")
        self.assertIn("redacted_", self.user.email)
        self.assertIsNone(self.user.phone_number)
        self.assertEqual(self.user.address_line1, "Redacted per privacy request")
        self.assertFalse(self.user.is_active)

    def test_logs_persist_after_user_anonymization(self):
        """DATA INTEGRITY: Ensure farm hours are NOT lost when a user is anonymized."""
        self.client.force_login(self.user)
        self.client.post(reverse("delete_account"))

        self.log_entry.refresh_from_db()
        self.assertIsNotNone(self.log_entry)
        self.assertEqual(self.log_entry.volunteer, self.user)

        total_hours = LogEntry.objects.filter(farm=self.farm).aggregate(
            Sum("duration_hours")
        )["duration_hours__sum"]
        self.assertEqual(total_hours, Decimal("4.50"))
