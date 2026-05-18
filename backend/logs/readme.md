# Logs App 🕒

This app is the transactional heartbeat of the platform. It handles the submission, validation, and storage of volunteer hours (`LogEntry`), and serves as the personalized "Volunteer Dashboard" where users can view their progress, pacing, and historical impact.

---

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints for this app:*

* **Form Multi-Tenancy (CRITICAL):** The `LogEntryForm` overrides the `__init__` method to accept a `user` keyword argument. This is strictly required to filter the `crop` dropdown so volunteers only see crops belonging to their specific `farm`. If you instantiate this form in a view, you MUST pass `user=request.user`.
* **Smart Form Validation:** The `LogEntryForm.clean()` method dictates conditional logic for crops. If the activity is "Off Season" (O) or "Move Dirt" (M), it forces the crop to `None`. For all plant-based activities (Planting, Tending, etc.), it strictly requires a crop.
* **Data Preservation Policy:** The `LogEntry` model uses `on_delete=models.SET_NULL` for both the `volunteer` and `crop` ForeignKeys. This is intentional. Do NOT change these to `CASCADE`. If a manager deletes a volunteer or a crop, the historical hours must remain intact so the farm's overall analytics and historical records are not destroyed.
* **Plotly Rendering Difference:** Unlike the `analytics` app (which serves charts via HTMX endpoints), the personal dashboard charts in this app are generated directly inside the synchronous `log_hours_view` and passed to the template context. Do not attempt to refactor these into HTMX endpoints unless explicitly instructed.
* **Decimal Math:** `duration_hours` uses a `DecimalField` instead of a `FloatField` to ensure exact mathematical aggregations. Maintain this standard.

---

## 🏗 Core Architecture & Models (`models.py`)

### `LogEntry`
The single transactional record of a volunteer's shift.

**Key Fields & Built-In Protections:**
1. **The "Time Machine" Blocker:** A custom validator (`validate_not_in_future`) strictly prevents users from logging hours for dates that haven't happened yet.
2. **The "Nuclear Option" Blocker:** As mentioned above, `SET_NULL` prevents the destruction of historical farm data if a user or crop is removed.
3. **Double Shifts Allowed:** The `unique_together` constraint was intentionally removed. Volunteers *are* allowed to log multiple shifts of the exact same activity/crop on the exact same day.
4. **Qualitative Notes:** Includes a `notes` TextField (max 2000 chars) for volunteers to record field observations, pest reports, or task details.

---

## 📡 Views & Features (`views.py`)

### The Dashboard & Entry View (`log_hours_view`)
* **URL:** `/log-hours/`
* **Function:** A hybrid view that handles both the `POST` request for logging new shifts and the `GET` request for rendering the volunteer's personal dashboard. Wraps database writes in a `try/except` block to log exceptions via Sentry/Audit without crashing the frontend.

**Key Analytical Engines within the View:**
* **The Pacing Engine:** Calculates how many hours per week a volunteer needs to work to meet their `WorkCommitment` target by the `Farm.season_end`. Safely handles edge cases like pre-season buffering and division-by-zero protections in the final days of the season.
* **Year-Based History Paginator:** Calculates the distinct years a user has logged hours and provides HTMX-ready pagination variables (`prev_year`, `next_year`) so users can seamlessly browse past shifts without reloading the page.
* **Fun Stats & Gamification:** Dynamically calculates the volunteer's "Top Veggie" and "Top Activity" for the current year. Generates "Season Badges" (⭐) based on the distinct number of years the user has logged hours (including their `legacy_years_volunteered` offset).

### The Plotly Fleet
The view generates four distinct `plotly.graph_objects` charts, stripped of their JS payloads, for the personal dashboard:
1. **Veggie Breakdown:** `go.Pie` showing season hours dedicated to specific crops.
2. **Activity Breakdown:** `go.Pie` showing season hours by task (Planting, Harvesting, etc.).
3. **Farm-Wide Comparison:** `go.Bar` (Horizontal Stacked). Compares the user's specific hours on a crop versus the rest of the farm's hours on that same crop.
4. **Lifetime Crop Mastery:** `go.Bar` (Horizontal). A leveling-up style chart showing all-time cumulative hours dedicated to each crop across all years.

---

## 📁 File Manifest

* **`models.py`**: Defines the `LogEntry` transaction, activity choices, and data-preservation rules.
* **`forms.py`**: Contains `LogEntryForm` with dynamic multi-tenant querysets and smart `clean()` conditional logic. Also injects Tailwind CSS logic into the form widgets.
* **`views.py`**: The massive controller handling shift ingestion, error catching, math aggregations (`Sum()`), and Plotly visualization generation.
* **`urls.py`**: Maps the single `/log-hours/` route.
* **`admin.py`**: Exposes the `LogEntry` to superusers with `list_filter` configured for quick sorting by Farm and Date.

---

## 🔗 Cross-App Dependencies
* **`farms` app:** `LogEntry` is heavily reliant on `Farm`, `Crop`, and `WorkCommitment` to accurately route data, filter form dropdowns, and calculate pacing.
* **`accounts` app:** Ties every entry to a `CustomUser`.