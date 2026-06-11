import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_customuser_admin_add_page(admin_client):
    """
    Simulates a superuser clicking 'Add User' in the admin panel.
    This catches FieldErrors where admin.py references deleted model fields.
    """
    url = reverse('admin:accounts_customuser_add')
    response = admin_client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_customuser_admin_changelist(admin_client):
    """Ensures the main user list page loads without crashing."""
    url = reverse('admin:accounts_customuser_changelist')
    response = admin_client.get(url)
    assert response.status_code == 200