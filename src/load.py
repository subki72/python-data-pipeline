import os
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from sqlalchemy import create_engine

def save_to_csv(df, filename="products.csv"):
    """Saves dataframe to CSV file."""
    try:
        if df is None or df.empty:
            return False
        df.to_csv(filename, index=False)
        print(f"[SUCCESS] Data saved to {filename}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save to CSV: {e}")
        return False

def save_to_google_sheets(df, json_keyfile="google-sheets-api.json", spreadsheet_name="Fashion_Data"):
    """Saves dataframe to Google Sheets."""
    try:
        if df is None or df.empty:
            return False
            
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_file(json_keyfile, scopes=scopes)
        client = gspread.authorize(credentials)
        
        sheet = client.open(spreadsheet_name).sheet1
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
        
        print("[SUCCESS] Data saved to Google Sheets")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save to Google Sheets: {e}")
        return False

def save_to_postgresql(df, db_url, table_name="fashion_products"):
    """Saves dataframe to PostgreSQL database."""
    try:
        if df is None or df.empty:
            return False

        engine = create_engine(db_url)
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        
        print(f"[SUCCESS] Data saved to PostgreSQL (table: {table_name})")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save to PostgreSQL: {e}")
        return False