import os
from pathlib import Path
import environ
import sentry_sdk
import sys

TESTING = "test" in sys.argv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    # Set casting and default values
    DEBUG=(bool, False)
)

# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# If the .env file is missing (like on GitHub Actions), fallback to a dummy key
SECRET_KEY = env("SECRET_KEY", default="django-insecure-github-actions-dummy-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

# Pull allowed hosts from .env, default to local development
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "phonenumber_field",  # <-- Add this!
    "accounts",  # <-- Our custom user app
    "django_q",  # <-- ADD THIS
    "farms",
    "logs",
    "crispy_forms",
    "crispy_tailwind",
    "axes",
    "analytics",
    "tailwind",
    "theme",
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "accounts.middleware.RequireEmailMiddleware",
    "farms.middleware.ActiveFarmMiddleware",
    "accounts.middleware.RequireWaiverMiddleware",
]

ROOT_URLCONF = "helpfarmersfarm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "helpfarmersfarm.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")}
# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Tell Django to use our custom user model
AUTH_USER_MODEL = "accounts.CustomUser"

LOGIN_REDIRECT_URL = "/log-hours/"
LOGOUT_REDIRECT_URL = "/"

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# --- AXES SECURITY SETTINGS ---
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",  # Axes checks for lockouts first
    "django.contrib.auth.backends.ModelBackend",  # Then Django checks the password
    "accounts.backends.EmailOrUsernameModelBackend",  # <-- THE FIX: Our new dual-login backend
]

AXES_FAILURE_LIMIT = 5  # 5 failed attempts allowed
AXES_COOLOFF_TIME = 1  # Lock out for 1 hour
AXES_RESET_ON_SUCCESS = True  # Reset the counter if they log in successfully

# --- EMAIL CONFIGURATION ---
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp-relay.brevo.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="hello@helpingfarmersfarm.com")

# Media Files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Tailwind Engine
TAILWIND_APP_NAME = "theme"
INTERNAL_IPS = [
    "127.0.0.1",
]

# --- LOGGING CONFIGURATION ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file_errors": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "django_errors.log",
            "formatter": "verbose",
        },
        "file_audit": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "django_audit.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": True,
        },
        "audit": {
            "handlers": ["file_audit"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# --- SECURITY & HTTPS HEADERS ---
# These are only activated in production when DEBUG is False AND we aren't running tests.
if not DEBUG and not TESTING:
    # Force all HTTP traffic to redirect to secure HTTPS
    SECURE_SSL_REDIRECT = True

    # Ensure session and CSRF cookies are only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Prevent browsers from guessing content types
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Enable the browser's built-in XSS protection
    SECURE_BROWSER_XSS_FILTER = True

    # HTTP Strict Transport Security (HSTS)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

sentry_sdk.init(
    dsn="https://6fe60ceecc320e972d9561523f35dc8d@o4511152203759616.ingest.us.sentry.io/4511411108511744",
    # --- NEW: Dynamically tag the environment ---
    environment="development" if DEBUG else "production",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    profiles_sample_rate=1.0,
)

# --- STRIPE BILLING ---
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# --- CLOUDFLARE TURNSTILE ---
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="1x0000000000000000000000000000000AA")

# --- PHONE NUMBER FORMATTING ---
PHONENUMBER_DEFAULT_REGION = "US"

# --- DJANGO-Q2 BACKGROUND WORKER ---
Q_CLUSTER = {
    "name": "HelpFarmersQueue",
    "workers": 1,  # Only process one PDF at a time to save RAM
    "recycle": 500,  # Restart worker occasionally to clear memory leaks
    "timeout": 60,  # Kill task if a PDF takes longer than 60 seconds
    "compress": True,  # Save DB space
    "save_limit": 250,  # Keep the last 250 success receipts in the DB
    "queue_limit": 500,  # Max tasks waiting in line
    "cpu_affinity": 1,  # Restrict worker to a single CPU core
    "label": "Django Q",
    "orm": "default",  # Use your existing PostgreSQL database as the broker
}

TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default=None)
