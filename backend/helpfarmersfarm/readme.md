# Helping Farmers Farm Core Configuration ⚙️

This directory (`Helping Farmers Farm/`) acts as the root command center for the entire Django project. It dictates the global settings, security policies, error tracking, installed applications, and root URL routing. 

**This is not a functional app; it is the infrastructure that holds the apps together.**

---

## 🤖 LLM Context & Architectural Rules
*If you are an AI, LLM, or new developer reading this repository, adhere strictly to the following constraints for this module:*

* **Environment Variables (CRITICAL):** Do NOT hardcode secrets or environment-specific variables (like `ALLOWED_HOSTS` or `DATABASES`) into `settings.py`. We use `django-environ`. Any new API keys or sensitive data must be wrapped in `env()` and added to the `.env` file structure.
* **Testing & Security Headers:** `settings.py` includes a custom `TESTING = 'test' in sys.argv` flag. This flag specifically disables strict HTTPS headers (`SECURE_SSL_REDIRECT`, etc.) during local automated testing to prevent the Django test client from crashing with `301` redirect errors. Do not remove this logic.
* **Custom User Model:** The project explicitly uses `AUTH_USER_MODEL = "accounts.CustomUser"`.
* **Form Rendering:** Global form rendering is handled by `crispy-tailwind`. Do not suggest adding separate form rendering libraries.
* **Media Serving:** `urls.py` is configured to serve user uploads (like Base64 avatars) locally *only* when `settings.DEBUG` is True. Do not suggest adding production media serving logic to `urls.py`. Production media is handled by the web server (Nginx/Apache) or an object store.

---

## 📂 Core Files & Responsibilities

### 1. `settings.py` (The Master Config)
This file orchestrates the entire platform. Key integrations include:

* **Security & Authentication (`django-axes` & Custom Backends):** * Uses `axes.backends.AxesBackend` as the primary defense to track and lock out brute-force attacks (`AXES_FAILURE_LIMIT = 5`).
  * Uses a custom `accounts.backends.EmailOrUsernameModelBackend` to allow users to log in with either a username or an email seamlessly.
* **Strict HTTPS:** When `DEBUG=False` and `TESTING=False`, strict security headers are enabled, including HSTS (`SECURE_HSTS_SECONDS`), forced SSL redirects, and secure CSRF/Session cookies.
* **Dual-Channel Logging:** * **Errors:** Catches `ERROR` level events and writes them silently to a local `django_errors.log` file.
  * **Audit:** A custom `audit` logger catches `INFO` level events (like manager actions or legacy database imports) and writes them to `django_audit.log` for a permanent paper trail.
* **Error Tracking (Sentry):** `sentry_sdk` is initialized here, with dynamic environment tagging (`"development" if DEBUG else "production"`) to keep error logs cleanly separated in the Sentry dashboard.
* **Database:** Hardcoded to use PostgreSQL via the `DATABASE_URL` environment string.
* **Tailwind CSS:** Configured to watch the `theme` app via `TAILWIND_APP_NAME = "theme"`.

### 2. `urls.py` (The Root Dispatcher)
This file delegates incoming HTTP traffic to the respective micro-apps.

**The Routing Map:**
* `/accounts/` -> Delegates to standard Django Auth (login/logout/password resets) and custom profile/avatar/claim views.
* `/farm/` -> Delegates to the `farms` app (Manager dashboards, commitment toggles, and multi-tenant management).
* `/analytics/` -> Delegates to the `analytics` app (HTMX endpoints for server-side Plotly chart generation).
* `/log-hours/` -> Delegates to the `logs` app (Transactional time tracking).
* `/` (Root) -> Serves the public `landing.html` directly via a `TemplateView`.
* `/admin/` -> The standard Django superuser backend.

### 3. `wsgi.py` & `asgi.py`
Standard Django deployment entry points.
* `wsgi.py` is currently utilized by Gunicorn (the Python WSGI HTTP Server) during the final production deployment on the Linux server. 
* `asgi.py` is pre-configured and available if the platform ever transitions to asynchronous workflows (like WebSockets for live chat or live notifications).