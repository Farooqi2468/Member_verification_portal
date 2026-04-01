# QR Code Generator Application

This is a Django-based web application designed to generate and store QR codes associated with Person records. 

## Features
- Create and manage Person records.
- Automatically generate unique QR codes for each Person record.
- Store details such as Name, CNIC, Phone, Address, and more.
- Built utilizing Django and Python.

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
python manage.py runserver
```

Once the server begins running, open your web browser and navigate to:
- Main App Interface: `http://127.0.0.1:8000/`
- Django Admin Panel: `http://127.0.0.1:8000/admin/`

## Project Structure

- `manage.py`: Django's command-line utility for local administrative tasks.
- `qrproject/`: Project configuration (settings, master routing etc).
- `qrapp/`: Contains logic for dealing with models (e.g., `Person`), endpoints, and generating the QR codes.
- `media/`: Directory designated for holding generated QR codes and file uploads.
- `requirements.txt`: The definitive list of Python package dependencies needed for startup.
