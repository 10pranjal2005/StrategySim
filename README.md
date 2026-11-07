# StrategySim

**Strategic Intelligence and Decision Support Platform**

StrategySim is a web-based strategic intelligence and decision-support application designed around the Indian electric two-wheeler (EV) industry. It brings company intelligence, competitor analysis, strategic frameworks, supply-chain intelligence, scenario simulation, and strategic decision-making into one platform.

The project uses **VoltEdge Motors** as its hypothetical target company for demonstration purposes. Sample companies, suppliers, competitors, and market information are illustrative and should not be interpreted as verified industry data.

## Features

### 1. Company and Industry Intelligence
- Company information management
- Competitor records and relationship management
- Industry intelligence

### 2. Strategic Analysis
- SWOT Analysis
- Porter's Five Forces
- Value Chain Analysis

### 3. Supply Chain Intelligence
- Supplier Network management
- Component management
- Supplier–component mapping
- Supplier relationships and facilities
- Dependency-related information

### 4. Scenario Simulator
Supports six scenario types:
- Supplier Price Increase
- Supplier Unavailability
- Raw Material Shortage
- Demand Decline
- Competitor Entry
- Substitute Technology

### 5. Strategic Decisions
- Decision matrix creation
- Alternative and criterion management
- Weighted evaluation
- Alternative ranking and comparison

### 6. Reports
- Company Intelligence reports
- Strategic Analysis reports
- Supply Chain Intelligence reports
- Scenario Simulation reports
- Strategic Decisions reports
- PDF generation and report history

### 7. User and Access Management
- User registration and authentication
- Password hashing
- Role-based access control
- Audit logging
- CSRF protection

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | HTML5, Tailwind CSS, Vanilla JavaScript |
| Backend | Python, Flask |
| Database | SQLite |
| Data Analysis | Pandas, NumPy |
| Network Analysis | NetworkX |
| Visualization | Plotly.js |
| PDF Generation | ReportLab |
| Authentication | Flask-Login, Werkzeug |
| Form Security | Flask-WTF |
| Testing | pytest, pytest-cov |

## Project Structure

```text
StrategySim/
├── app/
│   ├── auth/
│   ├── companies/
│   ├── competitors/
│   ├── evidence/
│   ├── five_forces/
│   ├── reports/
│   ├── scenario_simulator/
│   ├── strategic_analysis/
│   ├── strategic_decisions/
│   ├── suppliers/
│   ├── swot/
│   ├── services/
│   ├── templates/
│   ├── static/
│   └── database/
├── docs/
├── scripts/
├── tests/
├── instance/
├── run.py
├── requirements.txt
├── .env.example
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11 or a compatible Python version
- pip
- Git

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd StrategySim
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a reference.

Set a strong, unique secret key before running the application. Do not commit `.env` or production credentials.

### 5. Run the application

```powershell
python run.py
```

Open the local address displayed in the terminal in your browser.

## User Roles

StrategySim uses role-based access control:

| Role | Access |
|---|---|
| Administrator | Full application and user administration access |
| Analyst | View and manage permitted strategic analysis and decision records |
| Viewer | Read-only access to permitted records |

## Database and Data

The development application uses SQLite through Python's built-in `sqlite3` module.

The local database and generated reports are stored under the `instance/` directory. These files are intentionally excluded from version control.

**Important:** The repository does not contain the developer's local database or existing records. A fresh installation may require the application's database initialization and setup procedures.

## Testing

The project uses pytest and pytest-cov.

Run the test suite with:

```powershell
pytest
```

For coverage:

```powershell
pytest --cov=app
```

## Security Notes

- Never commit `.env`, secret keys, database files, or private backups.
- Use a unique production secret key.
- Enable secure cookies and HTTPS in production.
- Restrict access according to user roles.
- Use persistent production database and file storage when deploying.

## Deployment

The application is currently developed around Flask and local SQLite storage. Before production deployment, configure a persistent database and suitable persistent storage for generated PDF reports. Serverless hosting environments may not preserve local filesystem changes between requests.

## Project Status

StrategySim has implemented its core intelligence and decision-support modules, including company and competitor intelligence, strategic analysis, supplier network management, scenario simulation, strategic decisions, and PDF reporting.

Further deployment and production-readiness work remains.

## Disclaimer

StrategySim is an academic and demonstration project. VoltEdge Motors and other demonstration entities are hypothetical. Illustrative data and simulation outputs are not investment, procurement, financial, or business advice.

---

**StrategySim — Strategic Intelligence. Structured Analysis. Better Decisions.**