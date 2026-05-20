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
    path("profile/", views.profile_view, name="profile"),
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
    path("update-email/", views.update_email_view, name="update_email"),
    # NEW: The Claim Flow
    path("setup-access/", views.claim_account_search, name="claim_search"),
    path("setup-access/<int:user_id>/", views.claim_account_setup, name="claim_setup"),
    path("sign-waiver/", views.sign_waiver_view, name="sign_waiver"),
]
