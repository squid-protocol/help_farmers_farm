from django.urls import path
from . import views

urlpatterns = [
    path(
        "create-checkout-session/",
        views.create_checkout_session,
        name="create_checkout_session",
    ),
    path("success/", views.billing_success, name="billing_success"),
    path("portal/", views.customer_portal, name="customer_portal"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
]
