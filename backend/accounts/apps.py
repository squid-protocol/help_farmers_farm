import os
import threading
import webbrowser
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # The auto-reloader actually runs the code twice on startup.
        # This 'RUN_MAIN' check ensures we only open the browser once!
        if os.environ.get("RUN_MAIN") == "true":

            def open_browser():
                webbrowser.open("http://127.0.0.1:8000/accounts/login/")

            # Set a tiny 1.5-second delay to give the server time to fully bind to the port
            threading.Timer(1.5, open_browser).start()
