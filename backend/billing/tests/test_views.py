from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from django.contrib.auth import get_user_model
from farms.models import Farm
from accounts.models import FarmMembership
import stripe

User = get_user_model()


class BillingCheckoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(name="Stripe Test Farm")

        # FIX: Added an email address so the middleware lets them pass
        self.user = User.objects.create_user(
            username="treasurer",
            email="treasurer@example.com",
            password="securepassword",
            role="farm_manager",
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)
        self.checkout_url = reverse("create_checkout_session")

    def test_anonymous_user_cannot_access_checkout(self):
        """Ensure unauthenticated users are kicked to login."""
        response = self.client.post(self.checkout_url, {"price_id": "price_123"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    @patch("stripe.checkout.Session.create")
    def test_successful_checkout_redirects_to_stripe(self, mock_stripe_create):
        """Ensure a valid request gets a 303 redirect to Stripe's hosted portal."""
        self.client.force_login(self.user)
        # Mock what Stripe returns when a session is successfully created
        mock_stripe_create.return_value.url = "https://checkout.stripe.com/test-url"

        response = self.client.post(self.checkout_url, {"price_id": "price_valid_123"})

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.url, "https://checkout.stripe.com/test-url")
        # Verify we passed the Farm ID to Stripe so the webhook knows who paid
        mock_stripe_create.assert_called_once()
        call_kwargs = mock_stripe_create.call_args[1]
        self.assertEqual(call_kwargs["client_reference_id"], str(self.farm.id))

    def test_checkout_fails_gracefully_without_price_id(self):
        """Ensure we don't crash if the HTML form is tampered with and sends no price."""
        self.client.force_login(self.user)
        response = self.client.post(self.checkout_url, {})  # Empty payload

        # Should redirect back to pricing page
        self.assertRedirects(response, reverse("pricing"))

    @patch("stripe.checkout.Session.create")
    def test_checkout_handles_stripe_api_outage(self, mock_stripe_create):
        """Ensure the app doesn't crash if Stripe's servers go down."""
        self.client.force_login(self.user)
        mock_stripe_create.side_effect = stripe.error.APIConnectionError(
            "Stripe is down"
        )

        response = self.client.post(self.checkout_url, {"price_id": "price_123"})

        # Should catch the error and cleanly redirect back to pricing
        self.assertRedirects(response, reverse("pricing"))

    def test_billing_success_page_loads(self):
        """Ensure the post-checkout success page renders correctly."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("billing_success"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "billing/success.html")

    def test_checkout_get_request_redirects_to_pricing(self):
        """Ensure users cannot GET the checkout URL directly."""
        self.client.force_login(self.user)
        response = self.client.get(self.checkout_url)

        # They should be safely kicked back to the pricing page
        self.assertRedirects(response, reverse("pricing"))


class BillingWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook_url = reverse("stripe_webhook")

        # Farm 1: Unpaid, waiting for checkout
        self.new_farm = Farm.objects.create(name="New Farm", is_paid=False)

        # Farm 2: Active subscriber
        self.active_farm = Farm.objects.create(
            name="Premium Farm", is_paid=True, stripe_customer_id="cus_test999"
        )

    # --- SECURITY TESTS ---

    @patch("stripe.Webhook.construct_event")
    def test_webhook_rejects_invalid_signature(self, mock_construct):
        """Ensure hackers cannot spoof Stripe webhooks."""
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Bad sig", "sig_header"
        )
        response = self.client.post(
            self.webhook_url, data="fake_payload", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_rejects_malformed_json_payload(self, mock_construct):
        """Ensure the webhook returns a 400 Bad Request if the payload is broken JSON."""
        mock_construct.side_effect = ValueError("Invalid JSON payload")

        # Firing absolute garbage data at the webhook
        response = self.client.post(
            self.webhook_url,
            data="not_json_just_random_text",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    # --- SUCCESS LIFECYCLE TESTS ---

    @patch("stripe.Webhook.construct_event")
    def test_webhook_checkout_completed_upgrades_farm(self, mock_construct):
        """Ensure a successful payment unlocks the farm and saves the customer ID."""
        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(self.new_farm.id),
                    "customer": "cus_new_123",
                }
            },
        }

        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # Verify database changes
        self.new_farm.refresh_from_db()
        self.assertTrue(self.new_farm.is_paid)
        self.assertEqual(self.new_farm.stripe_customer_id, "cus_new_123")

    # --- EVICTION LIFECYCLE TESTS ---

    @patch("stripe.Webhook.construct_event")
    def test_webhook_payment_failed_revokes_access(self, mock_construct):
        """Ensure an expired card instantly shuts off premium access."""
        mock_construct.return_value = {
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_test999"}},  # Matches active_farm
        }

        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # Verify eviction
        self.active_farm.refresh_from_db()
        self.assertFalse(self.active_farm.is_paid)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_subscription_deleted_revokes_access(self, mock_construct):
        """Ensure a cancelled subscription shuts off premium access."""
        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_test999"}},  # Matches active_farm
        }

        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # Verify eviction
        self.active_farm.refresh_from_db()
        self.assertFalse(self.active_farm.is_paid)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_ignores_unknown_customers_safely(self, mock_construct):
        """Ensure the system doesn't crash if Stripe sends data for a deleted database row."""
        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_ghost_000"}},  # Does not exist in DB
        }

        response = self.client.post(self.webhook_url, content_type="application/json")
        # Should silently ignore it and return 200 to Stripe
        self.assertEqual(response.status_code, 200)

    def test_webhook_rejects_forged_payloads(self):
        """SECURITY: Ensure hackers cannot fake successful payment webhooks."""
        # Create a farm to test against
        farm = Farm.objects.create(name="Webhook Farm", stripe_customer_id="cus_123")

        fake_payload = (
            '{"type": "checkout.session.completed", "data": {"object": {"client_reference_id": "'
            + str(farm.id)
            + '"}}}'
        )

        # Send the payload WITHOUT the cryptographic Stripe-Signature header
        response = self.client.post(
            reverse("stripe_webhook"),
            data=fake_payload,
            content_type="application/json",
        )

        # The system must aggressively reject it
        self.assertEqual(response.status_code, 400)
        farm.refresh_from_db()
        self.assertFalse(farm.is_paid)


class BillingPortalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farm = Farm.objects.create(
            name="Portal Test Farm", stripe_customer_id="cus_portal123"
        )
        self.user = User.objects.create_user(
            username="portal_manager",
            email="portal@example.com",
            password="securepassword",
            role="farm_manager",
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, is_approved=True)
        self.portal_url = reverse("customer_portal")

    def test_get_request_redirects_safely(self):
        """Ensure users cannot GET the portal URL directly."""
        self.client.force_login(self.user)
        response = self.client.get(self.portal_url)
        self.assertRedirects(response, reverse("manager_dashboard"))

    def test_missing_customer_id_shows_error(self):
        """Ensure farms without a Stripe ID are caught gracefully."""
        self.farm.stripe_customer_id = None
        self.farm.save()
        self.client.force_login(self.user)

        response = self.client.post(self.portal_url)
        self.assertRedirects(response, reverse("manager_dashboard"))

    @patch("stripe.billing_portal.Session.create")
    def test_successful_portal_redirects_to_stripe(self, mock_portal_create):
        """Ensure a valid POST request generates a 303 redirect to the portal."""
        self.client.force_login(self.user)
        mock_portal_create.return_value.url = (
            "https://billing.stripe.com/p/session/test"
        )

        response = self.client.post(self.portal_url)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.url, "https://billing.stripe.com/p/session/test")
        mock_portal_create.assert_called_once()

    @patch("stripe.billing_portal.Session.create")
    def test_portal_handles_api_outage(self, mock_portal_create):
        """Ensure we don't crash if Stripe goes down."""
        self.client.force_login(self.user)
        mock_portal_create.side_effect = stripe.error.APIConnectionError("Stripe down")

        response = self.client.post(self.portal_url)
        self.assertRedirects(response, reverse("manager_dashboard"))


class WebhookEdgeCaseTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook_url = reverse("stripe_webhook")

    @patch("stripe.Webhook.construct_event")
    def test_webhook_ignores_missing_farm_safely_on_checkout(self, mock_construct):
        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {"client_reference_id": "999999", "customer": "cus_123"}
            },
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_ignores_missing_farm_on_payment_failed(self, mock_construct):
        mock_construct.return_value = {
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_ghost"}},
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_ignores_missing_farm_on_subscription_deleted(self, mock_construct):
        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_ghost"}},
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)


class WebhookSubscriptionUpdatedTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook_url = reverse("stripe_webhook")
        self.farm = Farm.objects.create(
            name="Upgrade Farm",
            is_paid=True,
            stripe_customer_id="cus_upgrade_123",
            subscription_tier="starter",
        )

    @patch("stripe.Webhook.construct_event")
    def test_webhook_upgrades_tier_to_growth(self, mock_construct):
        """Ensure a plan change updates the subscription tier string."""
        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_upgrade_123",
                    "status": "active",
                    "items": {
                        "data": [{"price": {"id": "price_1TbLHZ6EZATAzdVSRo4kyEjN"}}]
                    },
                }
            },
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        self.farm.refresh_from_db()
        self.assertEqual(self.farm.subscription_tier, "growth")
        self.assertTrue(self.farm.is_paid)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_upgrades_tier_to_institutional(self, mock_construct):
        """Ensure the new institutional tier maps correctly."""
        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_upgrade_123",
                    "status": "unpaid",
                    "items": {
                        "data": [{"price": {"id": "price_1TYsF54Q1x6w9f8FaXJmkcE1"}}]
                    },
                }
            },
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        self.farm.refresh_from_db()
        self.assertEqual(self.farm.subscription_tier, "institutional")

    @patch("stripe.Webhook.construct_event")
    def test_webhook_unpaid_status_revokes_access(self, mock_construct):
        """Ensure a failed recurring payment gracefully disables is_paid."""
        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_upgrade_123",
                    "status": "unpaid",
                    "items": {
                        "data": [{"price": {"id": "price_1TYsF54Q1x6w9f8FaXJmkcE1"}}]
                    },
                }
            },
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_paid)

    @patch("stripe.Webhook.construct_event")
    def test_webhook_ignores_missing_farm_on_update(self, mock_construct):
        """Ensure the system doesn't crash on an update for a deleted farm."""
        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_ghost_updater",
                    "status": "active",
                    "items": {
                        "data": [{"price": {"id": "price_1TbLHZ6EZATAzdVSRo4kyEjN"}}]
                    },
                }
            },
        }
        response = self.client.post(self.webhook_url, content_type="application/json")
        self.assertEqual(response.status_code, 200)
