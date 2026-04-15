# 🚩 PPP Member Verification Portal & QR Management System

[![Django](https://img.shields.io/badge/Framework-Django%206.0.3-092e20?logo=django)](https://www.djangoproject.com/)
[![Storage](https://img.shields.io/badge/Storage-AWS%20S3-FF9900?logo=amazons3)](https://aws.amazon.com/s3/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)

A high-performance, secure, and modern membership management portal designed for the **Pakistan Peoples Party (PPP)**. This portal facilitates the digital registration of members, automated generation of secure QR-coded membership cards, and robust administrative oversight with real-time analytics.

---

## 🚀 Key Features

### 💎 Digital Identity & QR Generation
- **Automated QR Codes:** Every member receives a unique QR code linked directly to their cloud-hosted profile.
- **Glossy Membership Cards:** Dynamic generation of vertical, three-band (Red, Black, Green) digital membership cards.
- **Secure Verification:** Scanned QR codes lead to a privacy-focused verification page that masks sensitive data (CNIC/Phone) while confirming identity.

### 📊 Reports & Advanced Analytics
- **Visual Growth Trends:** 6-month registration trends visualized with dynamic line charts.
- **Geographic Breakdown:** Doughnut charts showing member distribution across various Towns.
- **Registrar Performance:** Comparative bar charts identifying top-performing field staff.
- **Data Integrity Audit:** Real-time tracking of incomplete profiles (missing CNIC, Phone, or Address).
- **Printable Reports:** One-click "Print Report" functionality for physical documentation.
- **Role-Aware Data:** Super Admin usernames are only visible to other Super Admins, enforcing privacy by role.

### 🏠 Hierarchical Location Management
Comprehensive management of administrative boundaries including:
- **Towns, Zones, Union Councils (UCs), and Wards.**
- **Cascading Dropdowns:** Intelligent AJAX-based forms that prevent data entry errors.

### 🔐 Advanced Security & RBAC
- **Strict RBAC:** Superusers retain full control; Admins are restricted from managing Superuser accounts or groups.
- **Role-Based Visibility:** Super Admin entries are hidden from standard Admin views across users and reports.
- **Collapsible Role Descriptions:** An expandable reference panel on the user-creation form shows role summaries; Superuser details are only shown to Superusers.
- **Password Visibility:** Integrated toggle on login and settings screens for improved user experience.
- **Data Portability:** Filter and export member datasets directly to **CSV**.

### ⚙️ User Settings & Profile Management
- **Self-Service Profile Updates:** All users can update their display name and email from a dedicated Settings page.
- **Secure Password Change:** Inline password change form with current-password verification and real-time confirmation matching.
- **Consistent UI:** Settings page follows the same dashboard design language for a seamless experience.

### 🌙 Theme & Appearance
- **Components:** Tables, cards, pagination, sidebar, navigation bars, and filter sections all adapt correctly to the active theme.
- **Branded Favicon:** Application favicon derived from the PPP project logo for consistent browser-tab branding.

### ☁️ Cloud Infrastructure
- **AWS S3 Integration:** High-availability storage for all media assets using signed URLs for secure access.

---

## 🛠️ Tech Stack

- **Backend:** Python / Django 6.0.3
- **Database:** SQLite (Development) / Scalable to PostgreSQL (Production)
- **Cloud Storage:** Amazon S3 (via Boto3 & Django-Storages)
- **Frontend:** Vanilla CSS, JavaScript, Bootstrap 5, **Chart.js**
- **Utilities:** QRcode, Pillow (Image Processing)

---

## 📥 Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- AWS Account (for S3 storage)

### 2. Environment Setup
Clone the repository and activate the virtual environment:
```powershell
# Windows
.\.venv\Scripts\activate
```

### 3. Installation
Install the necessary dependencies:
```powershell
pip install -r requirements.txt
# Ensure storage drivers are installed
pip install django-storages boto3
```

### 4. Database Initialization
```powershell
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Administrative Account
```powershell
python manage.py createsuperuser
```

---

## ⚙️ Configuration

The system relies on AWS S3 for media storage. Ensure the following variables are correctly configured in `qrproject/settings.py` (or moved to an `.env` file for production):

| Variable | Description |
| :--- | :--- |
| `AWS_ACCESS_KEY_ID` | Your AWS Access Key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS Secret Key |
| `AWS_STORAGE_BUCKET_NAME` | S3 Bucket Name |
| `AWS_S3_REGION_NAME` | AWS Region (e.g., `us-east-1`) |

---

## 📂 Project Structure

```text
qrproject/
├── qrapp/                # Core Application Logic
│   ├── models.py         # Member, Town, Zone, UC, Ward models
│   ├── views.py          # Dashboard, Registration, Reports & Analytics
│   ├── forms.py          # Validated Data Entry & Profile/Password forms
│   ├── templates/        # Responsive HTML5 layouts
│   │   ├── reports.html  # Comprehensive analytics dashboard
│   │   ├── settings.html # User profile & password management
│   │   ├── create_user.html  # User creation with collapsible role guide
│   │   └── ...           # Registration, Members, Users templates
│   └── static/           # CSS, JS, and Branding Assets (favicon, logo)
├── qrproject/            # Project Configuration
│   ├── settings.py       # Global settings & AWS config
│   └── urls.py           # Main routing table
└── media/                # Local cache for QR codes (S3 backup)

```

---

## 📱 Mobile Responsiveness
The portal features a **collapsible sidebar navigation** and a **mobile-optimized bottom navigation bar** (including a Settings tab), ensuring that field registrars can easily use the system on smartphones and tablets.

---

© 2026 PPP Member Verification Portal. All Rights Reserved.
