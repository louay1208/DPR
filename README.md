# DPR Manager — Daily Production Report Web Application

A modern web application for extracting, validating, correcting, and exporting daily/monthly production data from Excel DPR files used in the oil & gas industry.

**Built with:** FastAPI (Python 3.12+) · Vanilla HTML/CSS/JS · SQLite · WebSockets

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Setup Guide (from scratch)](#setup-guide-from-scratch)
5. [Running the Application](#running-the-application)
6. [Default Credentials](#default-credentials)
7. [Project Structure](#project-structure)
8. [Configuration](#configuration)
9. [Database](#database)
10. [API Endpoints](#api-endpoints)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)

---

## Features

- **Excel DPR Parsing** — Extracts production data from complex multi-sheet Excel workbooks (Daily, Monthly, Well Test reports)
- **Auto-Correction Engine** — QC rules with configurable find/replace, negative value correction, hours capping
- **Unit Conversion** — SM3 ↔ NM3, MSCF → kSm3, BBL → m3, PSI → kPa (19 built-in conversions)
- **CSV Export** — Generates ProSource-compatible CSV output files
- **Concession Management** — Full CRUD for concessions, cell mappings, QC rules, UOM entries
- **Authentication & RBAC** — Token-based login with admin/user roles
- **Real-time Logging** — WebSocket-powered live log viewer
- **Dashboard** — Statistics and extraction history overview
- **Responsive SPA** — Works on desktop and mobile browsers

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│          Frontend (SPA — Vanilla HTML/CSS/JS)     │
│  index.html · login.html · register.html          │
└─────────────────────┬────────────────────────────┘
                      │ HTTP REST + WebSocket
┌─────────────────────▼────────────────────────────┐
│          Backend (FastAPI — Python 3.12+)          │
│                                                    │
│  Routers:  auth · extract · upload · settings      │
│            concessions · websocket                 │
│                                                    │
│  Services: ParserService · ExporterService         │
│            CorrectorService · LogService           │
│            MoulinetteLoader · ConfigStore           │
│                                                    │
│  Database: SQLite (dpr.db) — WAL mode              │
└──────────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| **Python** | ≥ 3.12 | [python.org/downloads](https://www.python.org/downloads/) |
| **uv** (package manager) | ≥ 0.4 | `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Git** | any | [git-scm.com](https://git-scm.com/) |

> **Note:** `uv` is used instead of `pip` for faster, reproducible dependency management. If you prefer `pip`, see the [alternative setup](#alternative-setup-with-pip) section.

---

## Setup Guide (from scratch)

### Step 1: Clone the Repository

```bash
git clone https://github.com/<your-username>/DPR.git
cd DPR
```

### Step 2: Install `uv` (if not already installed)

**Windows (PowerShell):**
```powershell
pip install uv
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify installation:
```bash
uv --version
```

### Step 3: Create Virtual Environment & Install Dependencies

```bash
uv sync
```

This single command:
- Creates a `.venv/` virtual environment (Python 3.12+)
- Installs all dependencies from `pyproject.toml` and `uv.lock`

### Step 4: Verify Installation

```bash
uv run python -c "import fastapi; import uvicorn; import openpyxl; import pandas; print('All dependencies OK')"
```

### Step 5: Run the Application

```bash
uv run uvicorn main:app --reload --port 8000
```

### Step 6: Open in Browser

Navigate to **[http://localhost:8000](http://localhost:8000)**

Login with the default credentials (see below).

---

## Running the Application

### Development (with auto-reload)

```bash
uv run uvicorn main:app --reload --port 8000
```

### Production

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

> **Note:** SQLite does not support multiple concurrent writers, so `--workers 1` is required.

### Custom Port

```bash
uv run uvicorn main:app --reload --port 3000
```

---

## Default Credentials

On first startup, the database is seeded with a default admin account:

| Field | Value |
|-------|-------|
| **Email** | `admin@etap.com` |
| **Password** | `admin` |
| **Role** | `admin` |

> ⚠️ **Change the default password immediately after first login.**

---

## Project Structure

```
DPR/
├── main.py                    # FastAPI entry point
├── pyproject.toml             # Python dependencies & project metadata
├── uv.lock                   # Locked dependency versions
├── dpr.db                    # SQLite database (included with sample data)
├── .gitignore
├── README.md
│
├── app/                      # Backend application
│   ├── __init__.py
│   ├── config.py             # Application configuration & paths
│   ├── core/
│   │   ├── events.py         # Startup/shutdown hooks
│   │   └── security.py       # JWT token & auth helpers
│   ├── models/
│   │   ├── schemas.py        # Pydantic models (DTOs)
│   │   └── config_models.py  # Concession/mapping models
│   ├── routers/
│   │   ├── auth.py           # Authentication & user management
│   │   ├── extract.py        # Data extraction & export endpoints
│   │   ├── upload.py         # File upload management
│   │   ├── settings.py       # App configuration & dashboard
│   │   ├── concessions.py    # Concession CRUD, QC rules, UOM
│   │   └── websocket.py      # WebSocket log streaming
│   └── services/
│       ├── database.py       # SQLite schema, migrations, connection
│       ├── parser.py         # DPR Excel extraction engine
│       ├── corrector.py      # Auto-correction & QC engine
│       ├── exporter.py       # CSV export for ProSource
│       ├── logger.py         # Singleton log service + WebSocket
│       ├── config_store.py   # SQLite CRUD for config data
│       ├── cell_reader.py    # Excel cell reference resolver
│       ├── moulinette_loader.py  # Moulinette Excel parser
│       ├── importer.py       # Bulk import from moulinette
│       ├── extraction_store.py   # Extraction history manager
│       ├── file_utils.py     # File validation utilities
│       └── filename_generator.py # DPR filename auto-generation
│
├── static/                   # Frontend (SPA)
│   ├── index.html            # Main application page
│   ├── login.html            # Login page
│   ├── register.html         # Registration page
│   ├── css/                  # Stylesheets
│   ├── js/                   # JavaScript modules
│   │   ├── app.js            # Main application logic
│   │   ├── auth.js           # Authentication module
│   │   └── i18n.js           # Internationalization (FR/EN)
│   └── img/                  # Static images
│
├── docs/                     # Documentation & reference files
│   ├── PMS_Loader_v2.8 (1).xlsm    # Moulinette reference workbook
│   ├── Mapping_*.xlsx        # Mapping reference files
│   ├── Abir.xlsx             # Sample DPR file for testing
│   ├── diagramme_*.puml      # UML diagram sources (PlantUML)
│   ├── diagramme_*.png/svg   # Rendered UML diagrams
│   └── diagramme_classes_fr.md  # Full class diagram documentation
│
├── tests/                    # Test scripts
│   ├── test_auth_rbac.py     # Authentication & RBAC tests
│   ├── test_extraction.py    # Extraction pipeline tests
│   ├── test_extraction_deep.py  # Deep extraction validation
│   ├── create_test_dpr.py    # Test DPR file generator
│   └── test_data/            # Test fixtures
│
├── uploads/                  # Uploaded DPR files (gitignored)
├── exports/                  # Generated CSV exports (gitignored)
├── logs/                     # Application logs (gitignored)
└── mappings/                 # Imported mapping files
```

---

## Configuration

### Application Settings

All configuration is in `app/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_TITLE` | `"DPR — Production Data Manager"` | Application title |
| `APP_VERSION` | `"1.0.0"` | Version string |
| `MAX_UPLOAD_SIZE` | `100 MB` | Maximum file upload size |
| `ALLOWED_EXTENSIONS` | `.xlsx, .xls, .xlsm, .csv` | Accepted file types |

### Runtime Configuration (via UI)

These settings are configured through the web interface under **Settings**:

- **DPR Folder** — Path to the folder containing DPR Excel files
- **Output Folder** — Path where exported CSV files are saved
- **SM3 ↔ NM3 factors** — Unit conversion factors

---

## Database

The application uses **SQLite** (`dpr.db`) with the following tables:

| Table | Purpose |
|-------|---------|
| `users` | User accounts & authentication |
| `user_sessions` | Active login sessions |
| `concessions` | Concession/operator configuration |
| `cell_mappings` | Excel cell reference mappings |
| `uom_entries` | Unit of measure conversions |
| `qc_rules` | QC cleaning find/replace rules |
| `naming_rules` | DPR filename generation rules |
| `parameters` | Key-value app configuration |
| `extractions` | Extraction run history |
| `extraction_rows` | Extracted data rows |
| `schema_version` | Migration tracking |

### Database Reset

To start with a fresh database:

```bash
# Backup current database (optional)
cp dpr.db dpr.db.backup

# Delete and restart (will auto-create with defaults)
rm dpr.db
uv run uvicorn main:app --reload --port 8000
```

The application auto-creates all tables and seeds default data (admin user, UOM entries, conversion parameters) on startup.

### Using the Included Database

The repository includes `dpr.db` pre-loaded with:
- Default admin account (`admin@etap.com` / `admin`)
- 19 unit conversion entries (MSCF, BBL, PSI, etc.)
- Sample concessions and mappings (if configured)

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login (returns token) |
| `POST` | `/auth/logout` | Logout (invalidate token) |
| `GET` | `/users/` | List all users (admin only) |
| `PUT` | `/users/{id}/role` | Update user role (admin only) |
| `DELETE` | `/users/{id}` | Delete user (admin only) |

### File Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload/` | Upload DPR files |
| `GET` | `/upload/` | List uploaded files |
| `DELETE` | `/upload/{file_id}` | Delete uploaded file |

### Data Extraction
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/data/extract` | Extract data from DPR files |
| `POST` | `/data/auto-correct/{id}` | Run auto-correction |
| `POST` | `/data/convert-units/{id}` | Convert units |
| `POST` | `/data/export-csv/{id}` | Export to CSV |
| `GET` | `/data/extractions` | List extraction history |

### Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings/config` | Get app configuration |
| `POST` | `/settings/config/paths` | Set folder paths |
| `POST` | `/settings/config/load-moulinette` | Import moulinette config |
| `GET` | `/settings/dashboard/insights` | Dashboard statistics |

### Concessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/config/concessions` | List concessions |
| `POST` | `/config/concessions` | Create concession |
| `PUT` | `/config/concessions/{id}` | Update concession |
| `DELETE` | `/config/concessions/{id}` | Delete concession |
| `GET/PUT` | `/config/concessions/{id}/mappings/{type}` | Cell mappings |
| `GET/POST/DELETE` | `/config/qc-rules` | QC rules CRUD |
| `GET/POST/DELETE` | `/config/uom` | UOM entries CRUD |

---

## Testing

### Run Tests

```bash
# Auth & RBAC tests
uv run python -m pytest tests/test_auth_rbac.py -v

# Extraction tests
uv run python -m pytest tests/test_extraction.py -v

# All tests
uv run python -m pytest tests/ -v
```

### Generate Test Data

```bash
uv run python tests/create_test_dpr.py
```

---

## Alternative Setup with pip

If you prefer using `pip` instead of `uv`:

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install fastapi[standard] uvicorn[standard] python-multipart openpyxl pandas websockets

# Install dev/test dependencies (optional)
pip install pytest httpx

# Run
uvicorn main:app --reload --port 8000
```

---

## Troubleshooting

### "Module not found" errors

Make sure you're using `uv run` prefix or that the virtual environment is activated:
```bash
uv run uvicorn main:app --reload --port 8000
```

### Port already in use

```bash
# Use a different port
uv run uvicorn main:app --reload --port 3000
```

### Database locked errors

SQLite supports only one writer at a time. Make sure only one instance of the server is running. Do not use `--workers > 1`.

### Excel parsing errors

- Ensure DPR files are `.xlsx` format (not `.xls`)
- Check that cell mappings are correctly configured in **Settings → Concessions**
- Verify the moulinette configuration has been imported

### Login not working

If the database was reset, the default admin account is recreated:
- **Email:** `admin@etap.com`
- **Password:** `admin`

---

## License

This project was developed as a graduation project (PFE) for ETAP (Entreprise Tunisienne d'Activités Pétrolières).
