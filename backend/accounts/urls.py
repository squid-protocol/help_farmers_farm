from django.urls import path
from . import views

urlpatterns = [
    # Your existing profile route
    path("profile/", views.profile_view, name="profile"),
    
    # THE MISSING LINK: This tells Django exactly where 'upload_avatar' lives
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
]