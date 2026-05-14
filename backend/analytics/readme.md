# Analytics App

This app functions as the dedicated data-visualization engine for the platform. It processes raw farm logs and serves dynamic, interactive Plotly charts as HTML fragments to be injected into the frontend via HTMX.

## 🤖 LLM Context & Architectural Rules
*If you are an AI or LLM reading this repository, adhere strictly to the following constraints for this app:*

* **HTMX Paradigm (CRITICAL):** These views do **NOT** return JSON data, and they do **NOT** render full HTML pages. They act as HTMX API endpoints that return localized HTML snippets (e.g., `analytics/partials/chart.html`). Do not suggest refactoring these to return `JsonResponse` or REST API formats.
* **Server-Side Rendering:** All charting logic is handled on the backend using Python. We query the database, process the data using `pandas`, build the visualization using `plotly.graph_objects`, and serialize it to an HTML div using `fig.to_html(full_html=False, include_plotlyjs=False)`. 
* **Frontend Plotly Dependency:** Because the backend strips the Plotly.js library out of the payload to save bandwidth (`include_plotlyjs=False`), the frontend base template MUST load the Plotly.js CDN in the `<head>`.
* **Data Processing:** Do not attempt to write complex, nested raw SQL or Django ORM annotations for the complex matrix transformations (like the 52-week heatmaps). The established pattern is to fetch raw `LogEntry` values, convert them to a `pandas` DataFrame, and use `df.groupby()` and `df.pivot()` to structure the data for Plotly.

---

## 🏗 Core Architecture & Data Flow

When a user interacts with a filter dropdown (e.g., changing the year or timeframe) on the frontend:
1. **HTMX Request:** The frontend issues a `GET` request to one of the `/api/chart/...` endpoints, passing the filter values as query parameters (`request.GET.get()`).
2. **Data Extraction:** The view queries the `LogEntry` model, filtering by the user's `farm` and the requested parameters.
3. **Pandas Transformation (ETL):** The raw QuerySet is passed into a Pandas DataFrame. Empty strings are standardized to `pd.NA`, dates are converted to ISO weeks (`WeekOfYear`), and data is pivoted into X/Y matrices.
4. **Plotly Generation:** `plotly.graph_objects` (`go.Figure`) is used to build the chart, defining discrete colorscales, hover templates, and responsive layouts.
5. **Response:** The Figure is compiled into an HTML string and injected into the `analytics/partials/chart.html` template, which HTMX seamlessly swaps into the user's DOM.

---

## 📡 API Endpoints (HTMX Partials)

All endpoints require authentication (`@login_required`) and automatically filter data to the `request.user.farm`.

### 1. Total Impact Chart (`get_impact_chart`)
* **URL:** `/api/chart/impact/`
* **Filters:** `timeframe` (days back), `crop_id`
* **Visualization:** Stacked Bar Chart (`go.Bar`). Shows the total hours spent on each crop, broken down and color-coded by specific activities (Planting, Tending, Harvesting, etc.).

### 2. Activity Heatmap (`get_activity_heatmap`)
* **URL:** `/api/chart/heatmap/`
* **Filters:** `year`
* **Visualization:** 52-Week Heatmap (`go.Heatmap`). Displays the *Dominant Activity* for each crop across the 52 weeks of the year. Uses a custom stepped discrete colorscale to map activities (Off-Season, Tending, Planting, Harvesting) to specific colors.

### 3. Term Occurrence Heatmap (`get_term_heatmap`)
* **URL:** `/api/chart/terms/`
* **Filters:** `year`
* **Visualization:** 52-Week Heatmap (`go.Heatmap`). Splits and stacks log occurrences to show how frequently a specific term (both Crop Names and Activity Labels) appears in the logs each week. 

### 4. Seasonal Timeline (`get_seasonal_timeline`)
* **URL:** `/api/chart/timeline/`
* **Filters:** `year`
* **Visualization:** Gantt-style Timeline (`go.Bar` with `base` offset). Aggregates the absolute `min` (Start Week) and `max` (End Week) for activities on a given crop, displaying horizontal bars that represent the duration of an activity season.

---

## 🔗 Cross-App Dependencies
* **`logs` app:** This app relies entirely on the `LogEntry` model to generate its data.
* **`farms` app:** Uses the `Farm` model via `request.user.farm` to isolate multi-tenant data.