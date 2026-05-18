# HelpFarmers 🌾

A robust, multi-tenant Django SaaS platform designed to manage farm volunteers, track logged hours securely, gamify the volunteer experience, and visualize complex agricultural impact metrics dynamically.

---

## 🏗 THE ARCHITECTURE (Micro-Services Map)

The project is strictly divided into domain-specific apps. **Do not mix their responsibilities.**

* **`accounts/` (Identity & Routing)**
  * Manages the custom User model and Role-Based Access Control (`account_manager`, `farm_manager`, `volunteer`).
  * Processes Base64 avatar uploads via Cropper.js.
  * Enforces the `RequireEmailMiddleware` tollbooth for legacy account claims.
* **`farms/` (Tenancy & Management)**
  * The core multi-tenant boundary. Holds the `Farm`, `Crop`, and `WorkCommitment` models.
  * Contains the interactive `manager_dashboard` for CRM-style administration.
  * Generates the manager-facing Volunteer Progress Report.
* **`logs/` (Transactional Core)**
  * Contains the `LogEntry` model (using exact `DecimalField` math).
  * Handles the volunteer pacing engine, badge gamification, and individual dashboard visualizations.
  * Protects against rapid "Double-Click" duplicate submissions.
* **`analytics/` (Data Visualization Engine)**
  * Acts purely as an HTMX API endpoint for rendering complex Plotly charts.
  * Transforms raw `LogEntry` QuerySets into Pandas DataFrames for deep aggregations (e.g., 52-week activity heatmaps).
* **`helpfarmers/` (System & Infrastructure)**
  * Core settings, security headers, routing, and Sentry error tracking.
  * Hosts the background Audit Logger for administrative tracking.
* **`theme/` (Frontend Pipeline)**
  * The local Node-based Tailwind CSS compilation pipeline.

---

## 🤖 UNIVERSAL LLM DIRECTIVES 
*If you are an AI, LLM, or new developer reading this repository, you MUST adhere strictly to the following core directives before suggesting any code changes:*

### 1. Frontend & UI Paradigm
* **HTMX over SPA:** This project uses **HTMX** for dynamic partial page updates. Do NOT suggest refactoring to React, Vue, or Angular. Views should return localized HTML fragments when handling HTMX requests.
* **Tailwind CSS (Local Pipeline):** We use `django-tailwind`. Do NOT suggest adding Tailwind via CDN. Forms are rendered using `crispy-tailwind`.
* **Plotly.js for Charts:** All data visualization is handled by Plotly. Charts are built server-side via Python/Pandas, stripped of their JS payload (`include_plotlyjs=False`), and rendered on the frontend using a globally loaded CDN script.

### 2. Database & Data Isolation (CRITICAL)
* **Row-Level Multi-Tenancy:** The entire platform revolves around the `farms.Farm` model. Almost every query involving Users, Crops, or Work Commitments **MUST** be filtered by `farm=request.user.farm`. Never write a view that leaks data across different farms.
* **Soft Deletes / Data Preservation:** We rely on `on_delete=models.SET_NULL` for historical data (like `LogEntry.volunteer` or `LogEntry.crop`). Do NOT suggest changing these to `CASCADE`, as deleting a volunteer or crop should never destroy a farm's historical impact analytics.
* **No Future Logging:** The `LogEntry` model strictly prohibits logging hours in the future via a custom validator.

### 3. Security & Infrastructure
* **Secret Management:** Hardcoded secrets are strictly forbidden. Use `django-environ` via the `.env` file. 
* **Strict HTTPS:** `helpfarmers/settings.py` enforces `SECURE_SSL_REDIRECT` and secure cookies when `DEBUG=False`. 
* **Testing Bypass:** A `TESTING = 'test' in sys.argv` flag safely bypasses SSL checks during local CI/CD runs so the Django test client doesn't crash on `301` redirects. Do not remove this.
* **Avatar Uploads:** Do NOT use standard `multipart/form-data` for avatars. The frontend uses Cropper.js to send a Base64 string to the backend, which decodes it into a `ContentFile`.

---

## 🛠 LOCAL DEVELOPMENT SETUP

### 1. Requirements
* Python 3.10+
* Node.js v20+ (Required for the `theme/` Tailwind compilation)
* PostgreSQL / SQLite (Local)

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
# .env
SECRET_KEY=your_secure_random_key_here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=postgres://user:password@127.0.0.1:5432/helpfarmers_db