import stripe
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

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
                client_reference_id=str(request.user.farm.id),
                success_url=request.build_absolute_uri(reverse("billing_success"))
                + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=request.build_absolute_uri(reverse("pricing")),
            )
            return redirect(checkout_session.url, code=303)

        except Exception as e:
            messages.error(
                request, f"There was an error connecting to Stripe: {str(e)}"
            )
            return redirect("pricing")

    return redirect("pricing")


@login_required
def billing_success(request):
    return render(request, "billing/success.html")


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
        # Invalid signature (Someone is trying to hack your webhook!)
        return HttpResponse(status=400)

    # Handle the successful checkout event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # We grab the Farm ID that we passed into client_reference_id during checkout
        # NOTE: We use dot notation here because the new Stripe SDK returns an object, not a dict!
        farm_id = session.client_reference_id

        if farm_id:
            print(f"💰 SUCCESS! Webhook received for Farm ID {farm_id}!")

            try:
                # Look up the farm in the database
                farm = Farm.objects.get(id=farm_id)

                # Update the new fields we just created!
                farm.is_paid = True
                farm.stripe_customer_id = session.customer

                farm.save()
                print(f"✅ Farm ID {farm_id} successfully upgraded in the database!")
            except Farm.DoesNotExist:
                print(f"❌ Error: Farm ID {farm_id} not found in database.")

    # Always return a 200 OK so Stripe knows we received it
    return HttpResponse(status=200)
