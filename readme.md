# Help Farmers Farm - Volunteer & Impact Tracking System

A robust, multi-tenant Django web application designed to manage farm volunteers, track logged hours securely, and visualize complex farm impact metrics dynamically. 

---

## 🤖 UNIVERSAL LLM DIRECTIVES & ARCHITECTURAL RULES
*If you are an AI, LLM, or new developer reading this repository, you MUST adhere strictly to the following core directives before suggesting any code changes:*

### 1. Frontend & UI Paradigm
* **HTMX over SPA:** This project uses **HTMX** for dynamic partial page updates. Do NOT suggest refactoring to React, Vue, or Angular. Views should return localized HTML fragments when handling HTMX requests.
* **Tailwind CSS (Local Pipeline):** We use a Node-based Tailwind compilation pipeline (`django-tailwind`) located in the `theme/` app. Do NOT suggest adding Tailwind via CDN. Forms are rendered using `crispy-tailwind`.
* **Plotly.js for Charts:** All data visualization is handled by Plotly. The charts are built server-side via Python/Pandas, stripped of their JS payload (`include_plotlyjs=False`), and rendered on the frontend using a globally loaded CDN script.

### 2. Database & Data Isolation (CRITICAL)
* **Row-Level Multi-Tenancy:** The entire platform revolves around the `farms.Farm` model. Almost every query involving Users, Crops, or Work Commitments **MUST** be filtered by `farm=request.user.farm`. Never write a view that leaks data across different farms.
* **Soft Deletes / Data Preservation:** We rely on `on_delete=models.SET_NULL` for historical data (like `LogEntry.volunteer` or `LogEntry.crop`). Do NOT suggest changing these to `CASCADE`, as deleting a volunteer or crop should never destroy a farm's historical impact analytics.
* **No Future Logging:** The `LogEntry` model strictly prohibits logging hours in the future via a custom validator.

### 3. Security & Infrastructure
* **Secret Management:** Hardcoded secrets are strictly forbidden. Use `django-environ` via the `.env` file. 
* **Strict HTTPS:** The `helpfarmers/settings.py` enforces `SECURE_SSL_REDIRECT` and secure cookies when `DEBUG=False`. 
* **Testing Bypass:** To prevent automated tests from failing due to `301 Redirects`, a `TESTING = 'test' in sys.argv` flag safely bypasses SSL checks during local CI/CD runs. Do not remove this.
* **Avatar Uploads:** Do NOT use standard `multipart/form-data` for avatars. The frontend uses Cropper.js to send a Base64 string to the backend, which decodes it into a `ContentFile`.

---

## 📂 APPLICATION BOUNDARIES (Micro-Services Map)

The project is strictly divided into domain-specific apps. **Do not mix their responsibilities.**

* **`accounts/` (Identity & Routing):** * Manages the `CustomUser` model (Inherits from `AbstractUser`).
  * Handles Role-Based Access (`account_manager`, `farm_manager`, `volunteer`).
  * Processes Base64 avatar uploads.
  * *Rule:* Never place charting logic or time-tracking logic here.
* **`farms/` (Tenancy & Management):** * Holds the core `Farm`, `Crop`, and `WorkCommitment` models.
  * Contains the multi-form `manager_dashboard` for admin control.
  * Generates the Progress Report for volunteers.
* **`logs/` (Transactional Core):** * Contains the `LogEntry` model (Uses exact `DecimalField` math).
  * Handles the volunteer pacing engine and individual dashboard generation.
  * Protects against rapid "Double-Click" duplicate submissions via `unique_together`.
* **`analytics/` (Data Visualization Engine):** * Acts purely as an HTMX API endpoint for rendering Plotly charts.
  * Transforms raw `LogEntry` QuerySets into Pandas DataFrames for complex aggregation (like 52-week heatmaps).
  * *Rule:* Do not return JSON here. Return `analytics/partials/chart.html`.

---

## 🛠 LOCAL DEVELOPMENT SETUP

### 1. Requirements
* Python 3.10+
* Node.js v20+ (Required for the `theme/` Tailwind compilation)
* PostgreSQL

### 2. Environment Variables
Create a `.env` file in the `backend/` directory:
```env
# backend/.env
SECRET_KEY=your_secure_random_key_here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

### 3. Installation & Bootstrapping
Activate your virtual environment and run the following from the `/backend/` directory:
```bash
# 1. Install Python packages
pip install -r requirements.txt

# 2. Install Node dependencies for Tailwind
python manage.py tailwind install

# 3. Run Database Migrations
python manage.py migrate
```

### 4. Running the Development Server
We use **Honcho** to manage multiple processes (Django + Tailwind Watcher). 
Do NOT run `manage.py runserver` manually. From the `backend/` directory, run:
```bash
honcho start
```
*Note: The `accounts` app contains a threading hook that will automatically open your default browser to `http://127.0.0.1:8000/accounts/login/` roughly 1.5 seconds after Honcho boots.*

---

## 🧪 TESTING & CI/CD
To run the automated test suite locally:
```bash
python manage.py test
```
*The test suite automatically bypasses HTTPS security headers so the native Django test client can execute standard HTTP requests without crashing.*

---

## 🚀 CURRENT ROADMAP & STATUS
* **Phase 1: Security Hardening** - COMPLETE (django-environ, HTTPS headers, .gitignore).
* **Phase 2: Documentation** - COMPLETE (LLM-optimized READMEs established).
* **Phase 3: Legacy Data ETL** - IN PROGRESS. We are currently building custom management commands in `utils/` to extract legacy flat files/SQL dumps, transform them to map to the new Row-Level Multi-Tenant schema, and load them into PostgreSQL.