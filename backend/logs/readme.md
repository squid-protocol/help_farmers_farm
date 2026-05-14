# Logs App

This app is the transactional heartbeat of the platform. It handles the submission, validation, and storage of volunteer hours (`LogEntry`), and serves as the personalized "Volunteer Dashboard" where users can view their progress, pacing, and historical impact.

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints for this app:*

* **Form Multi-Tenancy (CRITICAL):** The `LogEntryForm` overrides the `__init__` method to accept a `user` keyword argument. This is strictly required to filter the `crop` dropdown so volunteers only see crops belonging to their specific `farm`. If you instantiate this form in a view, you MUST pass `user=request.user`.
* **Data Preservation Policy:** The `LogEntry` model uses `on_delete=models.SET_NULL` for both the `volunteer` and `crop` ForeignKeys. This is intentional. Do NOT change these to `CASCADE`. If a manager deletes a volunteer or a crop, the historical hours must remain intact so the farm's overall analytics and historical records are not destroyed.
* **Plotly Rendering Difference:** Unlike the `analytics` app (which serves charts via HTMX endpoints), the personal dashboard charts in this app (Veggie and Activity pie charts) are generated directly inside the synchronous `log_hours_view` and passed to the template context. Do not attempt to refactor these into HTMX endpoints unless explicitly instructed.
* **Decimal Math:** `duration_hours` uses a `DecimalField` instead of a `FloatField` to ensure exact mathematical aggregations. Maintain this standard.

---

## 🏗 Core Architecture & Models

### `LogEntry`
The single transactional record of a volunteer's shift.

**Built-In Protections:**
1. **The "Time Machine" Blocker:** A custom validator (`validate_not_in_future`) strictly prevents users from logging hours for dates that haven't happened yet.
2. **The "Nuclear Option" Blocker:** As mentioned above, `SET_NULL` prevents the destruction of historical farm data if a user or crop is removed.
3. **The "Double-Click" Blocker:** A `unique_together` constraint on `['volunteer', 'crop', 'activity', 'date_logged', 'duration_hours']` prevents accidental duplicate database entries if a user rapidly clicks the submit button.

---

## 📡 Views & Features

### The Dashboard & Entry View (`log_hours_view`)
* **URL:** `/log-hours/`
* **Function:** A hybrid view that handles both the `POST` request for logging new shifts and the `GET` request for rendering the volunteer's personal dashboard.

**Key Analytical Engines within the View:**
* **The Pacing Engine:** Calculates how many hours per week a volunteer needs to work to meet their `WorkCommitment` target by the `Farm.season_end`. Safely handles edge cases like pre-season buffering and division-by-zero protections in the final days of the season.
* **Fun Stats & Gamification:** Dynamically calculates the volunteer's "Top Veggie" and "Top Activity" for the current year. Generates "Season Badges" (🌱) based on the distinct number of years the user has logged hours.
* **Personal Plotly Charts:** Generates two `go.Pie` charts (Activity Breakdown and Crop Breakdown) using customized discrete color palettes, stripped of the Plotly.js library payload (`include_plotlyjs=False`) to rely on the frontend CDN.

---

## 🔗 Cross-App Dependencies
* **`farms` app:** `LogEntry` is heavily reliant on `Farm`, `Crop`, and `WorkCommitment` to accurately route data and calculate pacing.
* **`accounts` app:** Ties every entry to a `CustomUser`.