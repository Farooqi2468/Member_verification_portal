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

### 🏠 Hierarchical Location Management
Comprehensive management of administrative boundaries including:
- **Towns**
- **Zones**
- **Union Councils (UCs)**
- **Wards**
- *Cascading dropdowns ensure data integrity during registration.*

### 🔐 Advanced Security & RBAC
- **Strict Hierarchy:** Superusers retain full control, while Admins are restricted from viewing or managing Superuser accounts.
- **Authenticated Access:** All management endpoints are protected via Django's authentication system.
- **Privacy First:** Data masking on public-facing verification endpoints.

### 📊 Administrative Dashboard & Analytics
- **Real-time Metrics:** Overview of total members, registrations by region, and staff performance.
- **Advanced Filtering:** Filter the entire directory by Town, Zone, UC, Ward, Registrar, or Registration Date.
- **Data Portability:** Export filtered member lists directly to **CSV** for offline reporting.

### ☁️ Cloud Infrastructure
- **AWS S3 Integration:** High-availability storage for all media assets (Profile Images & QR Codes) using signed URLs for secure access.

---

## 🛠️ Tech Stack

- **Backend:** Python / Django 6.0.3
- **Database:** SQLite (Development) / Scalable to PostgreSQL (Production)
- **Cloud Storage:** Amazon S3 (via Boto3 & Django-Storages)
- **Frontend:** Vanilla CSS, JavaScript, Bootstrap 5
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
| `AWS_S3_REGION_NAME` | AWS Region (e.g., `eu-north-1`) |

---

## 📂 Project Structure

```text
qrproject/
├── qrapp/                # Core Application Logic
│   ├── models.py         # Member, Town, Zone, UC, Ward models
│   ├── views/            # Dashboard, Registration, Verification logic
│   ├── templates/        # Responsive HTML5 layouts
│   └── forms.py          # Validated Data Entry forms
├── qrproject/            # Project Configuration
│   ├── settings.py       # Global settings & AWS config
│   └── urls.py           # Main routing table
├── media/                # (Local cache) Managed via S3
└── static/               # CSS, JS, and Branding Assets
```

---

## 📱 Mobile Responsiveness
The portal features a **collapsible sidebar navigation** and a **mobile-optimized bottom navigation bar**, ensuring that field registrars can easily use the system on smartphones and tablets.

---

© 2026 PPP Member Verification Portal. All Rights Reserved.
