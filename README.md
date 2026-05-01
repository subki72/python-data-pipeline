# ETL Pipeline Project

This project is an automated ETL (Extract, Transform, Load) Pipeline designed to scrape fashion product data from a mock e-commerce site, clean and transform the data, and load it into three distinct destinations:
1. A local CSV file.
2. A Google Sheets document.
3. A PostgreSQL database.

## Architecture

```text
etl_pipeline/
├── .env                      # Environment variables (e.g., DB_URL)
├── .gitignore                # Ignored files for git
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── main.py                   # Entry point / Orchestrator script
├── credentials/              # Sensitive credentials (e.g., Google API JSON)
├── data/                     # Output data directory
├── src/                      # Source code modules
│   ├── __init__.py
│   ├── extract.py            # Web scraping logic
│   ├── transform.py          # Data cleaning and transformation logic
│   └── load.py               # Database and API loading logic
└── tests/                    # Unit tests and coverage
    ├── __init__.py
    ├── test_extract.py
    ├── test_transform.py
    └── test_load.py
```

## Setup & Installation

### 1. Create and Activate Virtual Environment (Conda/Pip)

```bash
# Using conda
conda create -n etl_env python=3.10 -y
conda activate etl_env
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Credentials
- Place your `google-sheets-api.json` inside the `credentials/` folder.
- Create a `.env` file in the root directory and add your database URL:
```env
DB_URL="postgresql://user:password@host:port/dbname?sslmode=require"
```

## Running the Pipeline

Execute the main script to run the full ETL process:

```bash
python main.py
```

## Running Tests

To run unit tests:

```bash
python -m pytest tests
```

To run test coverage:

```bash
coverage run -m pytest tests
coverage report -m
```

## Links
- Google Sheets Result: https://docs.google.com/spreadsheets/d/1NSIsRGoX98STX3jL_PUON8NEtMhKVfHO8g1pK_MzhjE/edit?usp=sharing
