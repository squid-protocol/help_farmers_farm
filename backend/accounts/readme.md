# Accounts App

This app handles everything related to users, authentication, multi-tenant farm routing, and personalized volunteer impact tracking.

## Core Architecture

Instead of using Django's default User model, we use a `CustomUser` model (inheriting from `AbstractUser`) to allow for seamless multi-tenancy and advanced role management.

### Key Fields:
* **`farm` (ForeignKey):** Every user is strictly tied to a single `Farm` instance. This prevents data leakage between different organizations.
* **`role` (CharField):** Defines the user's permission level.
    * `account_manager`: System Administrator (Superuser access).
    * `farm_manager`: Local Admin. Can add crops, create volunteers, and define work commitments for their specific farm.
    * `volunteer`: Standard user. Can log hours and view their personal impact dashboard.
* **`work_commitment` (ForeignKey):** Links the user to a dynamically generated `WorkCommitment` (e.g., "Full Share - 80 hours") created by their Farm Manager.
* **`avatar` (ImageField):** Stores a customized profile picture.

## Features

### 1. Basic Profile Management (`profile_view`)
When a volunteer views their profile, they can manage their core user settings and identity:
* **Personal Details:** Update their first name, last name, email, and username.
* **Note:** The Personal Impact Dashboard (progress bars, Plotly charts, etc.) was previously located here but has been migrated to the `logs` app to centralize time-tracking visualizations.

### 2. Avatar Cropping (Cropper.js Integration)
To ensure all user profile pictures are perfectly square and don't break the UI, we handle image uploads entirely on the frontend before hitting the server:
1. The user selects an image via a hidden `<input type="file">`.
2. A modal pops up utilizing **Cropper.js**.
3. When the user clicks "Save", the cropped area is converted into a 300x300 Base64 string via the HTML5 Canvas API.
4. This lightweight string is submitted to the `upload_avatar` view, where Django decodes it using `ContentFile` and saves it securely to the `media/avatars/` directory with a randomized UUID filename to prevent browser caching issues.

## Dependencies
* `farms` app (For the `Farm` and `WorkCommitment` models)
* `logs` app (For calculating the impact dashboard)
* `plotly` (Python library for the dashboard charts)
* `cropperjs` (Frontend CDN for avatar manipulation)