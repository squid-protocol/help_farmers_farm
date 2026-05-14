# Help Farmers Farm - Core Project Configuration

This directory (`helpfarmers/`) acts as the root configuration folder for the entire Django project. It dictates the global settings, security policies, installed applications, and root URL routing.

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints:*

* **Environment Variables (CRITICAL):** Do NOT hardcode secrets or environment-specific variables (like `ALLOWED_HOSTS` or `DATABASES`) into `settings.py`. We use `django-environ`. Any new API keys or sensitive data must be wrapped in `env()` and added to the `.env` file structure.
* **Testing & Security Headers:** `settings.py` includes a custom `TESTING = 'test' in sys.argv` flag. This flag specifically disables strict HTTPS headers (`SECURE_SSL_REDIRECT`, etc.) during local automated testing to prevent the Django test client from crashing with `301` redirect errors. Do not remove this logic.
* **Custom User Model:** The project explicitly uses `AUTH_USER_MODEL = "accounts.CustomUser"`.
* **Form Rendering:** Global form rendering is handled by `crispy-tailwind`. Do not suggest adding separate form rendering libraries.
* **Media Serving:** `urls.py` is configured to serve user uploads (like Base64 avatars) locally *only* when `settings.DEBUG` is True. Do not suggest adding production media serving logic to `urls.py`.

---

## 📂 Core Files Breakdown

### 1. `settings.py`
The master configuration file. Key integrations include:
* **Security & Authentication:** Configured with `django-axes` for brute-force lockout protection.
* **Database:** Hardcoded to use PostgreSQL (`django.db.backends.postgresql`).
* **Logging:** Catches all `ERROR` level events and writes them silently to a local `django_errors.log` file.
* **Tailwind CSS:** Configured to watch the `theme` app via `TAILWIND_APP_NAME = "theme"`.

### 2. `urls.py`
The root URL dispatcher. It delegates traffic to the respective micro-apps:
* `/accounts/` -> Handles both Django Auth (login/logout) and custom profile/avatar views.
* `/farm/` -> Manager dashboards and multi-tenant routing.
* `/analytics/` -> HTMX endpoints for Plotly chart generation.
* `/` (Root) -> The main landing page and the `logs` app (time tracking).

### 3. `wsgi.py` & `asgi.py`
Standard Django deployment entry points. 
* `wsgi.py` will be utilized by Gunicorn during the final production deployment on the Linux server.