# Farms App

This app serves as the organizational core of the platform. It handles the "Row-Level Multi-Tenancy" architecture, allowing multiple independent farms to use the software simultaneously without their data overlapping. It also provides the main dashboard for Farm Managers to administrate their operations.

## Core Architecture: Multi-Tenancy

The central philosophy of this app is that almost every piece of data in the system belongs to a specific `Farm`. 

### Key Models:
* **`Farm`:** The top-level organizational unit.
* **`Crop` (ForeignKey to Farm):** Represents what a specific farm is growing. By isolating crops per farm, "Farm A" can have 5 varieties of tomatoes while "Farm B" only has 1, keeping their individual dropdowns clean.
* **`WorkCommitment` (ForeignKey to Farm):** Allows each farm to define its own customized share sizes and volunteer goals (e.g., "Full Share: 80 hours" vs "Standard Share: 50 hours").

## Features & Views

### 1. The Manager Dashboard (`manager_dashboard`)
This is the command center for Farm Managers. From a single unified page, managers can:
* Add new `Crops` to their farm's registry.
* Create new `Users` (Volunteers) directly tied to their farm.
* Define and add new `WorkCommitments`.
* View active rosters and crop lists.

### 2. Strict Security & Permissions
The app employs rigorous security checks to prevent privilege escalation and unauthorized access:
* **The `is_manager` Check:** Custom decorators (`@user_passes_test`) ensure only users with the `farm_manager` or `account_manager` roles can access administrative views.
* **Form-Level Security:** The `VolunteerCreationForm` explicitly intercepts the user creating the form. If a `farm_manager` is creating a new user, the form dynamically removes `account_manager` and `farm_manager` from the role dropdown, preventing them from granting privileges higher than their own.
* **Cross-Farm Data Protection:** Views like `volunteer_detail_view` explicitly check that `volunteer.farm == request.user.farm`. A manager from Farm A cannot view or edit a volunteer from Farm B.
* **Deletion Rules (`remove_user_view`):** Managers can remove volunteers, but strict rules prevent them from deleting themselves, deleting users outside their farm, or deleting system administrators.

### 3. Farm Impact Analytics
The `farm_impact_view` serves as the entry point for farm-wide data visualization, querying active crops and rendering the container where the `analytics` app will inject its HTMX-powered charts.

## Forms Integration
Instead of building complex HTML forms by hand, this app utilizes Django `ModelForm` classes (e.g., `WorkCommitmentForm`) with embedded Tailwind CSS classes within the widget `attrs`. This ensures the backend dictates the data structure while seamlessly matching the frontend UI design.

## Dependencies
* `accounts` app (For the `CustomUser` model and role checking)
* `logs` app (For querying total hours in the volunteer detail view)