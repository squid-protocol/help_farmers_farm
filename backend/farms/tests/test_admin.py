import pytest
from django.urls import reverse
from farms.models import Farm

@pytest.mark.django_db
def test_farm_admin_add_page(admin_client):
    """Ensures the Farm creation admin page loads properly."""
    url = reverse('admin:farms_farm_add')
    response = admin_client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_farm_admin_change_page(admin_client):
    """Ensures editing an existing Farm in the admin panel works."""
    # Create a dummy farm to edit
    farm = Farm.objects.create(name="Test Coverage Farm")
    url = reverse('admin:farms_farm_change', args=[farm.id])
    
    response = admin_client.get(url)
    assert response.status_code == 200