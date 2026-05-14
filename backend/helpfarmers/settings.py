from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-replace-this-with-a-real-secret-key-later"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",  # <-- Our custom user app
    "farms",
    "logs",
    "crispy_forms",
    "crispy_tailwind",
    "axes",
    "analytics",
    "tailwind",
    "theme",
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
]

ROOT_URLCONF = "helpfarmers.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # <--- THIS IS THE ONLY CHANGE
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

WSGI_APPLICATION = "helpfarmers.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "farm_logs",
        "USER": "farm_admin",
        "PASSWORD": "your_secure_password",  # Make sure this matches what you set in psql!
        "HOST": "localhost",
        "PORT": "5432",
    }
}


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

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Tell Django to use our custom user model
AUTH_USER_MODEL = "accounts.CustomUser"

LOGIN_REDIRECT_URL = "/log-hours/"

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"


# --- AXES SECURITY SETTINGS ---
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",  # Axes checks for lockouts first
    "django.contrib.auth.backends.ModelBackend",  # Then Django checks the password
]

AXES_FAILURE_LIMIT = 5  # 5 failed attempts allowed
AXES_COOLOFF_TIME = 1  # Lock out for 1 hour
AXES_RESET_ON_SUCCESS = True  # Reset the counter if they log in successfully

# During development, print emails to the console instead of actually sending them
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# settings.py (at the bottom)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

TAILWIND_APP_NAME = "theme"
INTERNAL_IPS = [
    "127.0.0.1",
]
