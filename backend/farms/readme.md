# Farms App

This app serves as the organizational core of the platform. It handles the "Row-Level Multi-Tenancy" architecture, allowing multiple independent farms to use the software simultaneously without their data overlapping. It also provides the main dashboard and reporting tools for Farm Managers.

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints for this app:*

* **Row-Level Multi-Tenancy (CRITICAL):** Almost every query in this app MUST be filtered by `farm=request.user.farm`. Never write a view or query that accidentally exposes `Crop`, `WorkCommitment`, or `User` data across different farms.
* **Form Submission Paradigm:** The `manager_dashboard` view handles four distinct forms (`CropForm`, `VolunteerCreationForm`, `WorkCommitmentForm`, `FarmSettingsForm`) on a single page. It differentiates them by checking for specific `name` attributes on the submit buttons (e.g., `if "submit_crop" in request.POST:`). Do not suggest breaking these into separate views unless explicitly requested.
* **Form Styling:** Forms are styled using Django `ModelForm` classes with embedded Tailwind CSS classes within the widget `attrs`. Do not suggest replacing this with manual HTML form rendering or third-party form packages.
* **Analytics Separation:** The `farm_impact_view` strictly serves the *shell* (the base HTML and dropdowns). The actual HTMX chart endpoints and Plotly logic live in the `analytics` app. Do not add charting logic to `farms/views.py`.

---

## 🏗 Core Architecture & Models

The central philosophy of this app is that data belongs to a specific `Farm`. 

* **`Farm`:** The top-level organizational unit. Contains meta-data like `season_start` and `season_end`.
* **`Crop` (ForeignKey to Farm):** Represents what a specific farm is growing. By isolating crops per farm, "Farm A" can have 5 varieties of tomatoes while "Farm B" only has 1, keeping their individual dropdowns clean.
* **`WorkCommitment` (ForeignKey to Farm):** Allows each farm to define its own customized share sizes and volunteer goals (e.g., "Full Share: 80 hours" vs "Standard Share: 50 hours").

---

## 📡 Views & Security Rules

### 1. The Manager Dashboard (`manager_dashboard`)
* **Function:** The command center for Farm Managers. From a single unified page, managers can add Crops, create Users, define Work Commitments, and update Farm Settings.
* **Access:** Protected by `@user_passes_test(is_manager)`.

### 2. Strict Security & Permissions
The app employs rigorous security checks to prevent privilege escalation and unauthorized access:
* **Form-Level Security:** The `VolunteerCreationForm` dynamically intercepts the `request_user`. If a `farm_manager` is creating a new user, the form strips `account_manager` and `farm_manager` from the role choices, preventing them from granting privileges higher than their own.
* **Cross-Farm Data Protection:** Views like `volunteer_detail_view` explicitly check `get_object_or_404(User, id=volunteer_id, farm=request.user.farm)`. A manager from Farm A cannot view or edit a volunteer from Farm B.
* **Deletion Rules (`remove_user_view`):** Managers can remove volunteers, but strict rules prevent them from:
    1. Deleting users outside their farm.
    2. Deleting system administrators (Account/Farm Managers).
    3. Deleting themselves.

### 3. The Progress Report (`progress_report_view`)
* **Function:** A manager-only view that tracks volunteer hour completion against their assigned `WorkCommitment` targets.
* **Data Flow:** Queries all active volunteers on the farm, calculates their `total_hours` for the current year using `LogEntry` aggregations, calculates the percentage completed (`pct`), and groups them by their `WorkCommitment.name`.
* **Sorting:** Groups are actively sorted so volunteers with the lowest progress appear at the top of the report.

---

## 🔗 Cross-App Dependencies
* **`accounts` app:** Provides the `CustomUser` model. `farms/forms.py` manipulates the `CustomUser` roles.
* **`logs` app:** The `volunteer_detail_view` and `progress_report_view` rely on `logs.LogEntry` to aggregate `Sum("duration_hours")`.
* **`analytics` app:** Provides the HTMX partials injected into `farm_impact.html`.