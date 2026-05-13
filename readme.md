# HelpFarmers: Farm Log & Analytics Dashboard

A comprehensive web application built to help community farms and agricultural projects track volunteer hours, manage crop seasons, and visualize labor data.

## 🚀 Features

* **Role-Based Dashboards:** Dedicated views for Farm Managers and Volunteers.
* **Streamlined Time Tracking:** Fast, intuitive logging for planting, tending, and harvesting activities.
* **Interactive Analytics:** Dynamic, HTMX-powered dashboards featuring Pandas and Plotly visualizations (Total Hours, Seasonal Activity Heatmaps, and Term Frequency).
* **Secure Profiles:** Custom user accounts with profile management, avatar cropping/uploading, and brute-force login protection via Django-Axes.

## 🛠️ Tech Stack

* **Backend:** Python 3.12, Django 5.x
* **Data Processing & Visualization:** Pandas, Plotly
* **Frontend:** HTML, Tailwind CSS, HTMX (for dynamic, SPA-like interactions without writing JavaScript)
* **Testing & Formatting:** `coverage`, `flake8`, `black`

## 📂 Project Structure

* `helpfarmers/` - Core Django project settings and routing.
* `accounts/` - Custom user models, authentication, and avatar management.
* `farms/` - Farm data models and Manager dashboards.
* `logs/` - Volunteer time entry models and forms.
* `analytics/` - Data aggregation and Plotly chart generation.

## 💻 Local Development Setup

To get this project running on your local machine, follow these steps:

**1. Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/help_farmers_farm.git
cd help_farmers_farm/backend
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv farm_venv
source farm_venv/bin/activate  # On Windows use: farm_venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Run database migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

**5. Create a superuser (Admin)**
```bash
python manage.py createsuperuser
```

**6. Start the development server**
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000` in your browser.

## 🧪 Testing and CI/CD

This project enforces strict code quality and test coverage. A GitHub Actions pipeline automatically runs on every push.

**Run the test suite with coverage:**
```bash
coverage run manage.py test
coverage report
```
*(Note: CI requires a minimum coverage of 75%)*

**Run the code formatter:**
```bash
black .
```