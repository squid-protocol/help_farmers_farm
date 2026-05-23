import stripe
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import logging

# IMPORTANT: Import your Farm model so the webhook can update it!
from farms.models import Farm

# Initialize Stripe with your secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_checkout_session(request):
    if request.method == "POST":
        price_id = request.POST.get("price_id")

        if not price_id:
            messages.error(request, "Invalid plan selected.")
            return redirect("pricing")

        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    },
                ],
                mode="subscription",
                allow_promotion_codes=True,
                client_reference_id=str(request.user.farm.id),
                success_url=(
                    request.build_absolute_uri(reverse("billing_success"))
                    + "?session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url=request.build_absolute_uri(reverse("pricing")),
            )

            # The exact 303 redirect Stripe requires to safely route to their hosted checkout
            response = redirect(checkout_session.url)
            response.status_code = 303
            return response

        except Exception as e:
            messages.error(
                request, f"There was an error connecting to Stripe: {str(e)}"
            )
            return redirect("pricing")

    return redirect("pricing")


@login_required
def billing_success(request):
    session_id = request.GET.get("session_id")
    farm = request.active_farm

    # If Stripe passed us a session ID, actively verify it right now
    if session_id and farm:
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            # If Stripe confirms they paid, preemptively upgrade the database
            # This beats the webhook race condition entirely!
            if session.payment_status == "paid":
                farm.is_paid = True

                # Capture the customer ID here as a failsafe
                if session.customer and not farm.stripe_customer_id:
                    farm.stripe_customer_id = session.customer

                farm.save()

        except Exception as e:
            # If the API ping fails for any reason, fail gracefully.
            # The background webhook will still eventually catch it.
            logger = logging.getLogger("django")
            logger.warning(
                f"Active Stripe verification failed for Session {session_id}: {e}"
            )

    return render(request, "billing/success.html")


@login_required
def customer_portal(request):
    if request.method == "POST":
        # Grab the farm securely assigned by your ActiveFarmMiddleware
        farm = request.active_farm

        # Safety check: Do they actually have a Stripe ID?
        if not farm.stripe_customer_id:
            messages.error(
                request, "We couldn't find an active billing account for this farm."
            )
            return redirect("manager_dashboard")

        try:
            # Generate the secure, temporary portal link
            portal_session = stripe.billing_portal.Session.create(
                customer=farm.stripe_customer_id,
                # Where Stripe should send them when they click "Return to App"
                return_url=request.build_absolute_uri(reverse("manager_dashboard")),
            )

            # The exact 303 redirect Stripe requires
            response = redirect(portal_session.url)
            response.status_code = 303
            return response

        except Exception as e:
            messages.error(request, f"Error connecting to billing portal: {str(e)}")
            return redirect("manager_dashboard")

    # Fallback if someone tries to GET this URL directly instead of POSTing
    return redirect("manager_dashboard")


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    event = None

    try:
        # Verify the message actually came from Stripe using your webhook secret
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    # ---------------------------------------------------------
    # 1. Handle Successful Checkout (The "Start")
    # ---------------------------------------------------------
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # We grab the Farm ID that we passed into client_reference_id
        farm_id = session.get("client_reference_id")

        if farm_id:
            try:
                farm = Farm.objects.get(id=farm_id)
                # FIX: Ensure this matches the actual field in farms/models.py
                farm.is_paid = True
                # CRITICAL: Save the Stripe Customer ID so we can look them up later if a card fails
                farm.stripe_customer_id = session.get("customer")
                farm.save()

                print(f"✅ Farm ID {farm_id} successfully upgraded!")
            except Farm.DoesNotExist:
                # The farm record was deleted locally or not yet created.
                # There is nothing to revoke, so it is safe to ignore this webhook.
                logger = logging.getLogger("django")
                logger.warning(
                    f"⚠️ Checkout webhook received for unknown farm ID {farm_id}."
                )

    # ---------------------------------------------------------
    # 2. Handle Failed Payments (Expired Cards, Insufficient Funds)
    # ---------------------------------------------------------
    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")

        if customer_id:
            try:
                farm = Farm.objects.get(stripe_customer_id=customer_id)
                farm.is_paid = False
                farm.save()
                print(f"⚠️ Farm {farm.name} payment failed. Premium access revoked.")
            except Farm.DoesNotExist:
                pass  # Farm doesn't exist, nothing to revoke

    # ---------------------------------------------------------
    # 3. Handle Cancelled Subscriptions (User cancels or Stripe gives up retrying)
    # ---------------------------------------------------------
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")

        if customer_id:
            try:
                farm = Farm.objects.get(stripe_customer_id=customer_id)
                farm.is_paid = False
                farm.save()
                print(
                    f"⚠️ Farm {farm.name} subscription ended. Premium access revoked."
                )
            except Farm.DoesNotExist:
                pass

    # ---------------------------------------------------------
    # 4. Handle Plan Upgrades/Downgrades & Past Due states
    # ---------------------------------------------------------
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        status = subscription.get("status")

        # Safely extract the new Stripe Price ID they just switched to
        try:
            new_price_id = subscription["items"]["data"][0]["price"]["id"]
        except (KeyError, IndexError):
            new_price_id = None

        if customer_id:
            try:
                farm = Farm.objects.get(stripe_customer_id=customer_id)

                # Map the Stripe Price ID to your internal database tiers
                if new_price_id == "price_1TYsDw4Q1x6w9f8FBWp82g03":
                    farm.subscription_tier = "starter"
                elif new_price_id == "price_1TYsF54Q1x6w9f8FaXJmkcE1":
                    farm.subscription_tier = "growth"
                elif (
                    new_price_id == "price_1TYsJj4Q1x6w9f8FpRlCUh0j"
                ):  # <-- PREMIUM ADDED
                    farm.subscription_tier = "institutional"

                # Ensure their paid status matches the new subscription state
                # 'past_due' occurs during the dunning grace period
                if status in ["active", "trialing", "past_due"]:
                    farm.is_paid = True
                else:
                    farm.is_paid = False

                farm.save()
                print(f"🔄 Farm {farm.name} subscription updated (Status: {status}).")

            except Farm.DoesNotExist:
                # Safely ignore webhooks for deleted farms
                pass

    # Always return a 200 OK so Stripe knows we received it
    return HttpResponse(status=200)
