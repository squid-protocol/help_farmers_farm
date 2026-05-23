from django.test import TestCase
from accounts.forms import ProfileUpdateForm


class ProfileUpdateFormTests(TestCase):
    def test_invalid_state_abbreviation_rejected(self):
        """Unhappy Path: Ensure users cannot submit full state names or numbers."""
        form = ProfileUpdateForm(
            data={
                "first_name": "Joe",
                "last_name": "Farmer",
                "email": "joe@test.com",
                "address_line1": "123 Dirt Road",
                "city": "Grand Rapids",
                "state": "Michigan",  # BAD DATA (Too long)
                "postal_code": "49503",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("state", form.errors)

    def test_invalid_zip_code_rejected(self):
        """Unhappy Path: Ensure users cannot submit letters in the ZIP code."""
        form = ProfileUpdateForm(
            data={
                "first_name": "Joe",
                "last_name": "Farmer",
                "email": "joe@test.com",
                "address_line1": "123 Dirt Road",
                "city": "Grand Rapids",
                "state": "MI",
                "postal_code": "ABCDE",  # BAD DATA (Letters)
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("postal_code", form.errors)
