# HelpFarmers - Backend Root 🚜

This directory (`/backend`) is the root of the HelpFarmers Django application. It contains the primary entry points for running the server, managing background processes, and interacting with the database, as well as the directories for all individual micro-apps.

---

## 🏗 The App Ecosystem (Domain Map)
The platform is strictly divided into domain-specific applications. **For deep technical details, architectural rules, and LLM directives, please read the `readme.md` located inside each app's folder.**

* ⚙️ **`helpingfarmersfarm/`**: The core configuration folder (Settings, Security Headers, Root URLs, Sentry, and Audit Logging).
* 👤 **`accounts/`**: Identity engine (Custom Users, RBAC roles, Cropper.js Avatars, and the Legacy Claim flow).
* 🌾 **`farms/`**: Multi-tenant boundaries, CRM-style Manager Dashboards, and the Global Pacing Engine.
* 🕒 **`logs/`**: The transactional core (Shift logging, double-click prevention, personal pacing, and badges).
* 📊 **`analytics/`**: The HTMX-driven Plotly engine (DataFrames, Heatmaps, and KPI dashboards).
* 🎨 **`theme/`**: The `django-tailwind` application housing the Node.js CSS build pipeline.

---

## 📂 Root File Manifest & Utilities

Aside from the apps themselves, this root directory contains several critical utility files that power the development and deployment pipelines.

### [cite_start]`Procfile` [cite: 648]
Used in conjunction with **Honcho** to manage multiple local development processes simultaneously. 
* [cite_start]**`web`**: Runs the standard Django development server (`python manage.py runserver`). [cite: 648]
* [cite_start]**`tailwind`**: Runs the Node watcher to compile Tailwind CSS on the fly (`python manage.py tailwind start`). [cite: 648]

### `generate_content.py`
[cite_start]A custom-built ingestion script designed specifically for LLM-assisted development. [cite: 3]
* [cite_start]**Function:** Walks the directory tree and bundles all relevant `.py`, `.html`, and configuration files into a single output file (`llm_context.txt`). [cite: 6, 7]
* [cite_start]**Filters:** Intelligently ignores massive, machine-generated folders (`__pycache__`, `node_modules`/`theme`, `farm_venv`, `.git`, `migrations`) and binary file extensions (`.sqlite3`, `.png`, etc.) to keep the token count lean and relevant. [cite: 3, 4, 5]

### `manage.py`
[cite_start]The standard Django command-line utility. [cite: 1] [cite_start]It dynamically sets the `DJANGO_SETTINGS_MODULE` to `helpingfarmersfarm.settings` and executes administrative tasks (migrations, superuser creation, shell access). [cite: 1]

---

## 🛠 Local Development Workflow

### 1. The Golden Rule of Booting Up
Do **not** run `python manage.py runserver` manually. 

Because this project relies heavily on a custom Tailwind CSS pipeline, you must run both the Django server and the Tailwind watcher simultaneously. To do this, simply run:
```bash
honcho start