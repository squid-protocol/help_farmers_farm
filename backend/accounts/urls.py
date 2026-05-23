from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import CustomLoginForm

urlpatterns = [
    # Override the default login to use our new label
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=CustomLoginForm),
        name="login",
    ),
    # Profile & Account Management
    path("profile/", views.profile_view, name="profile"),
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
    path("update-email/", views.update_email_view, name="update_email"),
    path("delete-account/", views.delete_account_view, name="delete_account"),
    # The Claim Flow
    path("setup-access/", views.claim_account_search, name="claim_search"),
    path("setup-access/<int:user_id>/", views.claim_account_setup, name="claim_setup"),
    # Compliance & Security
    path("sign-waiver/", views.sign_waiver_view, name="sign_waiver"),
    path(
        "verify-email/<str:token>/",
        views.verify_email_link_view,
        name="verify_email_link",
    ),
    # The New Registration Pipeline
    path("signup/", views.signup_gateway_view, name="signup_gateway"),
    path("signup/volunteer/", views.volunteer_signup_view, name="signup_volunteer"),
    path("signup/farm/", views.farm_signup_view, name="signup_farm"),
]
