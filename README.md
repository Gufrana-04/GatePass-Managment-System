# GIMA GatePass System

GIMA GatePass System is a Flask-based internal gatepass application backed by Oracle Database. It supports user login by site code, dashboard navigation, gatepass data entry, in/out processing, supplier and employee lookup, and list views for operational tracking.

## Features

- Site-based login flow with session handling
- Dashboard landing page after authentication
- Gatepass data entry screen
- Gatepass in/out entry screen
- Supplier and employee autocomplete API
- Gatepass list API for monthly tracking
- Department lookup API
- Oracle Database integration through the Oracle Instant Client

## Project Structure

- `app.py` - main Flask application and routes
- `config.py` - application configuration and database credentials
- `db.py` - reusable Oracle connection helper
- `query_test.py` - standalone database login query test script
- `test_db.py` - Oracle connection test script
- `templates/` - HTML templates for the user interface
- `static/` - CSS, JavaScript, fonts, and images

## Prerequisites

- Python 3.10+ recommended
- Oracle Database access
- Oracle Instant Client installed locally
- A valid database user, password, and DSN

## Installation

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Update `config.py` with your environment values:

```python
SYSTEM_NAME = "GatePass System"
SECRET_KEY = "your-secret-key"
DB_USER = "your-db-user"
DB_PASSWORD = "your-db-password"
DB_DSN = "your-host:1521/your-service"
ORACLE_CLIENT_PATH = r"C:\oracle\instantclient_19_29"
```

## Running the Application

Start the Flask app with:

```bash
python app.py
```

If your project uses a different entry point for local development, use that script instead.

## Main Pages

- `/login` - login page
- `/dashboard` - post-login dashboard
- `/transaction/Gatepass Data Entry` - gatepass entry screen
- `/transaction/Gatepass In Out Entry` - in/out entry screen

## API Endpoints

- `/api/sitecodes` - returns available site codes
- `/api/supplier/list` - returns supplier or employee lookup data
- `/api/gatepass/list` - returns gatepass records for a selected month
- `/api/department/list` - returns department data

## Database Notes

The application connects to Oracle in thick mode using the Oracle Instant Client path configured in `config.py`. Make sure the client path exists on your machine before starting the app.

## Troubleshooting

- If the app fails on startup, confirm `config.py` has valid values for `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `ORACLE_CLIENT_PATH`, and `SECRET_KEY`.
- If Oracle connection errors appear, verify the Instant Client installation and that the DSN is reachable.
- If templates do not load, confirm the required files are present in `templates/`.

## Security Notes

Do not commit real database credentials or secret keys to a public repository. For production use, move sensitive values to environment variables or a secure secret manager.

## License

Internal project. Add a license here if the repository will be shared externally.
