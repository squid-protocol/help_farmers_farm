# Accounts App 👤

The `accounts` app is the central identity and authentication engine of the HelpFarmers platform. It handles custom user modeling, role-based access control (RBAC), multi-tenant farm routing, and specialized onboarding flows for legacy volunteers.

---

## 🤖 LLM Context & Architectural Rules
*If you are an AI or new developer reading this repository, adhere strictly to the following constraints for this app:*

* **Custom User Model (`CustomUser`):** We do NOT use Django's default `User` model. Any foreign keys referencing users in other apps must use `settings.AUTH_USER_MODEL` or `get_user_model()`.
* **Avatar Upload Paradigm (CRITICAL):** Do **NOT** implement standard `multipart/form-data` file uploads for avatars. The frontend uses **Cropper.js** to crop images into a square, converts them to a Base64 string via the Canvas API, and POSTs the string to the `upload_avatar` view. The backend then decodes this string into a Django `ContentFile`. Do not alter this data flow.
* **Historical Context (Do Not Revert):** The volunteer's "Personal Impact Dashboard" (Plotly graphs, progress bars) was previously located in the `profile_view` of this app. It has been permanently migrated to the `logs` app to centralize time-tracking visualizations. Do not suggest adding charting logic back into the `accounts` views.
* **Local Dev Quirks:** `apps.py` contains a `threading.Timer` that automatically opens the browser to `/accounts/login/` when `honcho start` is run. Do not interpret this as production routing logic.

---

## 🏗 Core Architecture & Models (`models.py`)

### `CustomUser` (Inherits from `AbstractUser`)
Every user in the system is an instance of this model. It acts as the anchor for both permissions and multi-tenancy.

**Key Relational Fields:**
* **`farm` (ForeignKey -> `farms.Farm`):** The core multi-tenant link. Every user is strictly tied to a single Farm instance to prevent data leakage.
* **`work_commitment` (ForeignKey -> `farms.WorkCommitment`):** Links the user to a dynamically generated seasonal tier (e.g., "Full Share - 80 hours").
* **`legacy_years_volunteered`:** An integer offset for users who volunteered before the system was built, ensuring their lifetime badges and stats are accurate.

**Role Management (`role` CharField):**
1. `account_manager`: System Administrator (Superuser equivalent access).
2. `farm_manager`: Local Admin. Can manage volunteers and commitments for their specific `farm` only.
3. `volunteer`: Standard user. Can log hours and view personal metrics.
4. `friend`: Read-Only/Legacy status. Can view historical data but cannot log new shifts.

---

## 🛡 Authentication & Security Tollbooths

This app replaces standard Django authentication with a custom, user-friendly flow tailored for farmers and volunteers.

### 1. Dual-Login Backend (`backends.py`)
* **`EmailOrUsernameModelBackend`**: Overrides Django's default authentication to accept *either* a username or an email address in the login field. This is paired with `CustomLoginForm` (`forms.py`) which updates the frontend label to match.

### 2. The Email Tollbooth (`middleware.py`)
* **`RequireEmailMiddleware`**: Because legacy volunteers were imported without email addresses, this middleware acts as a strict checkpoint. If an authenticated user has an empty email field, they are locked out of the entire application and forcefully redirected to `/accounts/update-email/` until they provide one. 
* *Note:* It explicitly allows static and media files to pass through so the site's CSS doesn't break while they are trapped on the update screen.

---

## 🛤 The Legacy Claim Flow (`views.py` & `urls.py`)

Because thousands of volunteer logs were imported from a legacy SQLite database, many users exist in the system without passwords or emails. The "Claim Flow" allows them to securely take ownership of these ghost accounts.

1. **Step 1: Search (`claim_account_search`)** * URL: `/accounts/setup-access/`
   * Users search for their first or last name. The view queries the database for matching users who *do not* have an email address yet.
2. **Step 2: Setup (`claim_account_setup`)**
   * URL: `/accounts/setup-access/<user_id>/`
   * Using the `AccountClaimForm`, the user provides an email and creates a secure password. The backend hashes the password, saves the email, and automatically logs them in, securely finalizing their onboarding.

---

## 📁 File Manifest & Responsibilities

* **`admin.py`**: Customizes the Django admin panel (`CustomUserAdmin`) to expose the `role`, `farm`, and `work_commitment` fields for superusers.
* **`apps.py`**: Contains the application configuration and the local development `threading.Timer` that auto-opens the browser.
* **`backends.py`**: Houses the `EmailOrUsernameModelBackend` logic.
* **`forms.py`**: Defines the forms used in the UI: `ProfileUpdateForm`, `CustomLoginForm`, and `AccountClaimForm` (which includes password confirmation validation).
* **`middleware.py`**: Houses the `RequireEmailMiddleware` tollbooth logic.
* **`models.py`**: Defines the `CustomUser` schema and the `ROLE_CHOICES` hierarchy.
* **`urls.py`**: Maps the HTTP routes for login, profile editing, avatar uploads, and the legacy claim flow.
* **`views.py`**: The controller logic for handling form submissions, the Base64 Cropper.js image decoding (`upload_avatar`), and the onboarding pipeline.