# Accounts App

This app handles everything related to user identity, authentication, multi-tenant farm routing, and role-based permissions.

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints for this app:*

* **Custom User Model (`CustomUser`):** We do not use Django's default `User` model. Any foreign keys referencing users in other apps must use `settings.AUTH_USER_MODEL` or `get_user_model()`.
* **Avatar Upload Paradigm (CRITICAL):** Do **NOT** implement standard `multipart/form-data` file uploads for avatars. The frontend uses **Cropper.js** to crop images into a square, converts them to a Base64 string via the Canvas API, and POSTs the string to the `upload_avatar` view. The backend then decodes this string into a Django `ContentFile`. Do not alter this data flow.
* **Historical Context (Do Not Revert):** The volunteer's "Personal Impact Dashboard" (Plotly graphs, progress bars) was previously located in the `profile_view` of this app. It has been permanently migrated to the `logs` app to centralize time-tracking visualizations. Do not suggest adding charting logic back into the `accounts` views.
* **Local Dev Quirks:** `apps.py` contains a `threading.Timer` that automatically opens the browser to `/accounts/login/` when `honcho start` is run. Do not interpret this as production routing logic.

---

## 🏗 Core Architecture & Models

### `CustomUser` (Inherits from `AbstractUser`)
Every user in the system is an instance of this model, tying them to specific permissions and a specific farm.

**Key Relational Fields:**
* **`farm` (ForeignKey -> `farms.Farm`):** The core multi-tenant link. Every user is strictly tied to a single Farm instance to prevent data leakage.
* **`work_commitment` (ForeignKey -> `farms.WorkCommitment`):** Links the user to a dynamically generated tier (e.g., "Full Share - 80 hours") created by their Farm Manager.

**Role Management (`role` CharField):**
Defines the user's permission level.
1. `account_manager`: System Administrator (Superuser equivalent access).
2. `farm_manager`: Local Admin. Can manage volunteers and commitments for their specific `farm` only.
3. `volunteer`: Standard user. Can log hours and view personal metrics.
4. `friend`: Read-Only/Legacy status.

---

## 📡 Views & API Connections

### 1. Basic Profile Management (`profile_view`)
* **URL:** `/accounts/profile/`
* **Function:** Standard Django `ModelForm` (`ProfileUpdateForm`) handling updates to `first_name`, `last_name`, `email`, and `username`. 

### 2. Avatar Processing (`upload_avatar`)
* **URL:** `/accounts/upload-avatar/`
* **Function:** Acts as a lightweight API endpoint for the frontend Cropper.js script.
* **Data Flow:** 1. Receives `POST` containing `avatar_base64` (e.g., `"data:image/jpeg;base64,/9j/4AAQ..."`).
    2. Splits the MIME type header from the raw data.
    3. Generates a randomized UUID filename (e.g., `avatar_5_a1b2c3d4.jpeg`) to forcibly break browser caching of old avatars.
    4. Decodes the string and saves it to the user's `avatar` ImageField.

---

## 🔗 Cross-App Dependencies
* **`farms` app:** Provides the `Farm` and `WorkCommitment` models essential for user creation and routing.
* **`logs` app:** Relies heavily on the `CustomUser` model to attach time entries to specific individuals.