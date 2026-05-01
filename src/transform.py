import pandas as pd
from datetime import datetime

def clean_data(df):
    """Cleans and transforms extracted data."""
    try:
        df = df.dropna().copy()
        df = df.drop_duplicates(keep='first')

        df = df[~df['Title'].str.contains('Unknown Product', case=False, na=False)]
        df = df[~df['Price'].str.contains('Price Unavailable', case=False, na=False)]
        df = df[~df['Rating'].str.contains('Invalid Rating', case=False, na=False)]

        df['Price'] = df['Price'].astype(str).str.replace('$', '', regex=False)
        df['Price'] = df['Price'].astype(float) * 16000
        
        df['Rating'] = df['Rating'].astype(str).str.extract(r'(\d+\.\d+)').astype(float)

        df['Colors'] = df['Colors'].astype(str).str.extract(r'(\d+)').astype("Int64")

        df['Size'] = df['Size'].astype(str).str.replace('Size:', '', case=False).str.strip()
        df['Gender'] = df['Gender'].astype(str).str.replace('Gender:', '', case=False).str.strip()

        df['timestamp'] = datetime.now()

        return df

    except Exception as e:
        print(f"[ERROR] Error occurred during data transformation: {e}")
        return None