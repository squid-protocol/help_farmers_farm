# Farms App 🌾

This app serves as the organizational core of the platform. It handles the "Row-Level Multi-Tenancy" architecture, allowing multiple independent farms to use the software simultaneously without their data overlapping. It also acts as the primary CRM and reporting dashboard for Farm Managers.

---

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints for this app:*

* **Row-Level Multi-Tenancy (CRITICAL):** Almost every query in this app MUST be filtered by `farm=request.user.farm`. Never write a view or query that accidentally exposes `Crop`, `WorkCommitment`, or `User` data across different farms.
* **Form Submission Paradigm:** The `manager_dashboard` view handles four distinct form creations (`CropForm`, `VolunteerCreationForm`, `WorkCommitmentForm`, `FarmSettingsForm`) on a single page via `<dialog>` modals. It differentiates them by checking for specific `name` attributes on the submit buttons (e.g., `if "submit_crop" in request.POST:`). Do not suggest breaking these into separate views.
* **Form Styling:** Forms are styled using Django `ModelForm` classes with embedded Tailwind CSS classes within the widget `attrs`. Do not suggest replacing this with manual HTML form rendering or third-party form packages.
* **Analytics Separation:** The `farm_impact_view` strictly serves the *shell* (the base HTML and dropdowns). The actual HTMX chart endpoints and Plotly logic live in the `analytics` app. Do not add charting logic to `farms/views.py`.

---

## 🏗 Core Architecture & Models (`models.py`)

The central philosophy of this app is that data belongs strictly to a specific `Farm`. 

* **`Farm`:** The top-level organizational unit. Contains meta-data like `season_start` and `season_end`, which are critical for the pacing engine.
* **`Crop` (ForeignKey to Farm):** Represents what a specific farm is growing. By isolating crops per farm, "Farm A" can have 5 varieties of tomatoes while "Farm B" only has 1. Features an `is_active` boolean for soft-deleting.
* **`WorkCommitment` (ForeignKey to Farm):** Allows each farm to define its own customized share sizes and volunteer goals (e.g., "Full Share: 80 hours"). Features a visually helpful `symbol` (e.g., 🌕, 🌓) for UI dashboards.

---

## 📡 Views & Security Rules (`views.py`)

### 1. The Manager Command Center (`manager_dashboard`)
* **Function:** The master UI for Farm Managers. From a single unified page, managers can add Crops, create Users, define Work Commitments, and update Farm Settings via HTML5 `<dialog>` modals.
* **Features:** Calculates summary statistics (Active Volunteers, Active Crops), groups commitments, and pulls a feed of recent "Volunteer Field Notes" from the `logs` app.
* **Access:** Protected by `@user_passes_test(is_manager)`.

### 2. The Global Pacing Engine (`progress_report_view`)
* **Function:** Tracks volunteer hour completion against their assigned `WorkCommitment` targets. 
* **The Pacing Math:** Uses the `Farm.season_start` and `Farm.season_end` boundaries to calculate the `expected_pct` (the exact percentage of the season that has elapsed). This value is passed to the template to render a visual dart (🎯) on the progress bars, instantly showing managers who is falling behind pace.

### 3. Strict Security & Privilege Handling
The app employs rigorous security checks to prevent privilege escalation:
* **Form-Level Security (`forms.py`):** The `VolunteerCreationForm` and `VolunteerEditForm` dynamically intercept the `request_user`. If a `farm_manager` is interacting with the form, the backend strips `account_manager` and `farm_manager` from the role choices, preventing them from granting privileges higher than their own.
* **Cross-Farm Data Protection:** Views explicitly check `get_object_or_404(..., farm=request.user.farm)`. A manager from Farm A cannot view or edit an entity from Farm B.

### 4. Toggles & Inline Editing
* **Soft Deletes (`toggle_user_status_view`, `toggle_crop_status_view`):** Data is never destroyed. Managers can toggle `is_active` on users and crops to archive them.
* **Inline Edits (`edit_*_view`):** Dedicated routes for modifying existing Crops, Volunteers, and Commitments, re-using the secure form logic.

---

## 📁 File Manifest & UI Templates

* **`manager_dashboard.html`**: The massive, heavily-styled command center utilizing Tailwind grids, HTML dialog modals, and dynamic roster tabs (Active vs Total).
* **`progress_report.html`**: Iterates through grouped dictionary data to generate the tiered progress bar UI.
* **`farm_impact.html`**: The HTMX shell containing placeholders for the Plotly visual engine.
* **`admin.py`**: Cleanly exposes the internal models to superusers with `list_filter` and `search_fields` enabled for quick debugging.

---

## 🔗 Cross-App Dependencies
* **`accounts` app:** Provides the `CustomUser` model. `farms/forms.py` manipulates the `CustomUser` roles.
* **`logs` app:** The `volunteer_detail_view`, `manager_dashboard` (field notes), and `progress_report_view` rely on `logs.LogEntry` to aggregate data (`Sum("duration_hours")`).
* **`analytics` app:** Provides the HTMX partials injected into `farm_impact.html`.