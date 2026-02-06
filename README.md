# 📊 Enterprise Project Analytics Dashboard

A robust, data-driven web application designed to streamline project tracking and reporting. This tool ingests raw operational data via Excel, processes complex business logic using **Pandas**, and delivers actionable insights through an interactive **Django** dashboard.

## 🚀 Overview

Managing project lifecycles often involves decentralized spreadsheets and manual data crunching. This application centralizes that workflow, offering leadership and operational teams a single source of truth for:
* **Pre-Sales Analysis:** Tracking login dates, lead sources, and conversion probabilities.
* **Execution Monitoring:** visualizing "Post-Sales" performance, design stages, and operational bottlenecks.
* **Automated Reporting:** Generating formatted Excel reports (Summary & Detailed) instantly.

## ✨ Key Features

### 1. 📂 Data Ingestion Engine
* **Bulk Upload:** Accepts multi-sheet Excel files (Sales, Design, Operations).
* **Smart Sanitization:** Automatically cleans missing values (`NaN`), normalizes date formats, and maps non-standard column names to the database schema using **Pandas**.
* **Calculated Metrics:** Computes complex ratios (e.g., *Key Plans Ratio*, *Manpower Efficiency*) on the fly during import.

### 2. 📈 Interactive Dashboard
* **Dynamic Filtering:** Filter projects by Date Range, SBU (Strategic Business Unit), or specific Roles (e.g., Sales Head, Project Manager).
* **Live KPI Cards:** Instant visibility into "Pre-Stage" vs. "Execution Stage" project counts and metrics.
* **Searchable Dropdowns:** Custom-built filter components that allow searching within dropdown lists for better UX.

### 3. 📝 Reporting Module
* **Leadership Summary:** Aggregates high-level stats and conversion percentages into a downloadable Excel sheet.
* **Detailed Exports:** Provides granular, row-by-row project data for auditing purposes.
* **Live Web Tables:** Renders dataframes directly to HTML tables for quick reviews without downloading.

## 🛠️ Tech Stack

* **Backend:** Python 3.10+, Django 5.0
* **Data Processing:** Pandas, NumPy, OpenPyXL
* **Database:** SQLite (Default for Dev) / PostgreSQL (Production Ready)
* **Frontend:** HTML5, Bootstrap 5, Vanilla JavaScript
* **Deployment:** Compatible with PythonAnywhere, Render, and Vercel.

## 📋 Expected Data Structure

The application expects an Excel file (`.xlsx`) containing three specific sheets. The ingestion engine automatically maps the following column headers to the database.

> **Note:** The column names must match exactly (case-insensitive) for the metrics to calculate correctly.

### 1. Sheet: "Sales"
Required columns for Pre-Sales analysis:
* `Project Code` (Unique ID)
* `Project Name`
* `SBU` (Region/Unit)
* `Project Login Date` (Used for "Pre-Stage" filtering)
* `Stage` (Must contain 'Pre Sales' or 'Post Sales')
* `Sales Head` / `Sales Lead`

### 2. Sheet: "Design"
Required columns for Design KPIs:
* `Project Code`
* `Design Head` (DH) / `Design Lead` (DM)
* `Design ID` / `3D Visualizer`
* `No Key Plans Spaces` (Numerator for KPI)
* `Mapped Spaces` (Denominator for KPI)

### 3. Sheet: "Operation"
Required columns for Execution tracking:
* `Project Code`
* `Ops Head` / `Project Manager` (PM)
* `Project Start Date`
* `Project End Date`
* `Actual Manpower` / `Planned Manpower` (For Efficiency Ratio)

## ⚙️ Local Installation

Follow these steps to run the project locally on your machine.

**1. Clone the repository**
```bash
git clone [https://github.com/YOUR-USERNAME/Enterprise-Project-Dashboard.git](https://github.com/YOUR-USERNAME/Enterprise-Project-Dashboard.git)
cd Enterprise-Project-Dashboard
```

**2. Create a Virtual Environment**
```bash
# Windows
python -m venv venv
source venv/Scripts/activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install Dependencies**
```bash
pip install -r requirements.txt
```

**4. Apply Database Migrations**
```bash
python manage.py migrate
```

**5. Create a Superuser (Admin)**
```bash
python manage.py createsuperuser
```

**6. Run the Server**
```bash
python manage.py runserver
```
Access the dashboard at `http://127.0.0.1:8000`.

## 🔒 Privacy & Security Note

This repository contains the **source code logic only**.
* **No Data:** All database files (`db.sqlite3`) and raw Excel datasets are excluded via `.gitignore` to ensure client data privacy.
* **No Secrets:** Environment variables (Secret Keys, Debug Mode) should be configured locally in a `.env` file for production use.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
