# 🚜 Helping Farmers Farm: Monorepo Root

Welcome to the master repository for **[Helping Farmers Farm](https://www.helpingfarmersfarm.com)**. 

This repository houses the entire ecosystem required to run the platform, from the core application logic to the infrastructure configurations that deploy it to the production server.

---

## 🗺️ Repository Map

This repository is structured to separate application logic from infrastructure and utility scripts. If you are looking for specific application code, check the corresponding directories below.

* ⚙️ **`backend/`**: The heart of the platform. This directory contains the primary Django application, the Tailwind CSS build pipeline, and all domain-specific micro-apps (Farms, Logs, Analytics). **Start here for all web development.** *(See `backend/readme.md` for full architectural details).*
* 🌐 **`infra/`**: The deployment and infrastructure hub. This contains server configuration files, systemd daemon setups (Gunicorn, Qcluster), Nginx routing blocks, and deployment scripts. 
* 🛠️ **`utils/`**: Global utility scripts used for server maintenance, database backups, automated seed data generation, and administrative cron jobs.
* 👤 **`accounts/`**: Top-level identity and access management modules.
* 🗑️ **`temp/`**: Ephemeral storage for local testing, temporary CSV/PDF exports, and local logging. *(Note: This directory should generally be ignored by version control).*
* 📦 **`requirements.txt`**: The master Python dependency manifest required to build the virtual environment for the entire ecosystem.

---

## 🚀 Quick Start & Documentation

Because this is a multi-layered application, detailed documentation is stored alongside the code it describes. 

* **Web Development & Local Server:** Navigate to `/backend` and read the `readme.md` located there. It contains the exact commands (`honcho start`) required to boot the Django server and Tailwind CSS compiler simultaneously.
* **Server Deployment & Production:** See the documentation within `/infra` for the exact sequence of commands required to pull code, migrate the database, and restart the system daemons safely.

---

## 🔒 Security & Environment Notes
* **Never commit `.env` files.** All secrets, API keys (Stripe, AWS, Turnstile), and database credentials must be managed via secure environment variables on the production server.
* Ensure your Python virtual environment (`farm_venv`) is fully active before running any scripts from the `utils/` or `backend/` directories.