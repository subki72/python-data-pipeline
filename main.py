import os
from dotenv import load_dotenv

from src.extract import scrape_fashion_data
from src.transform import clean_data
from src.load import save_to_csv, save_to_google_sheets, save_to_postgresql

def run_pipeline():
    load_dotenv()
    print("=== Starting ETL Pipeline ===")
    
    raw_df = scrape_fashion_data(max_pages=50)
    
    clean_df = clean_data(raw_df)
    
    if clean_df is not None and not clean_df.empty:
        save_to_csv(clean_df, "data/products.csv")
        
        save_to_google_sheets(clean_df, "credentials/google-sheets-api.json", "ETL-Submission-Project")
        
        DB_URL = os.getenv("DB_URL")
        if not DB_URL:
            print("[ERROR] DB_URL not found in .env file")
            return
            
        save_to_postgresql(clean_df, DB_URL, "fashion_products")
        
    else:
        print("[WARNING] Pipeline stopped because data is empty.")

if __name__ == "__main__":
    run_pipeline()
    print("=== ETL Pipeline Completed ===")