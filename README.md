# PPP Membership Portal & QR Generator

This is a Django-based web application designed to manage membership records for the PPP, generating distinct digital membership profiles and QR codes for each registered member.

## Features

- **Member Registration & Management:** Create, update, and manage member profiles from a robust administrative dashboard.
- **Data Validation:** Ensures accurate record-keeping with enforced input formats:
  - **CNIC:** Must follow the `XXXXX-XXXXXXX-X` format.
  - **Phone:** Must follow the 11-digit Pakistani format `03XXXXXXXXX` without hyphens.
- **Dynamic Membership Cards:** Automatically generates a digital, glossy three-band (Red, Black, Green) membership card showing user details alongside a unique QR code.
- **QR Code Scanning:** Specifically tailored layout providing a standalone view to display scanned profile data securely, masking sensitive info like CNIC or Phone to maintain privacy.

## Getting Started

Follow these steps to set up and run the application on your local machine.

### Prerequisites
- Python installed on your system.

### 1. Activating the Virtual Environment

It is highly recommended to run this project inside an isolated virtual environment. A virtual environment folder named `.venv` already exists in the project directory.

**To activate it on Windows (Command Prompt or PowerShell):**
```powershell
.\.venv\Scripts\activate
```

*(If the virtual environment is corrupted or empty, you can recreate it by running `python -m venv .venv` first)*

### 2. Install Dependencies

Once the virtual environment is correctly activated, make sure all necessary library packages are installed:

```powershell
pip install -r requirements.txt
```
This application relies on:
- `Django`
- `qrcode`
- `Pillow`

### 3. Database Migrations

Apply the database migrations to build up your database structure (SQLite is used by default):

```powershell
python manage.py makemigrations
python manage.py migrate
```

### 4. Create a Superuser (Optional)

To access the backend Django admin panel, you can create an admin profile:

```powershell
python manage.py createsuperuser
```
Follow the on-screen prompts to set your desired username, email, and password.

### 5. Start the Application

Start the local development server by executing:

```powershell
python manage.py runserver 192.168.18.202:8000
```
*(Optionally, use just `python manage.py runserver` for localhost access)*

Once the server begins running, you can access the platform at:
- **Main Dashboard/Registration:** `http://192.168.18.202:8000/` (or `http://127.0.0.1:8000/`)
- **Django Admin Panel:** `http://192.168.18.202:8000/admin/`

## Project Structure

- `manage.py`: Django's command-line utility for local administrative tasks.
- `qrproject/`: Project core configurations (settings, master routing, etc).
- `qrapp/`: Contains forms, models, endpoints, views, and logic generating the digital membership profiles and QR codes.
- `media/`: Directory designated for saving the generated QR images.
- `requirements.txt`: The definitive list of Python package dependencies needed for startup.
