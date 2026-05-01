import unittest
from unittest.mock import patch
import pandas as pd
from src.load import save_to_csv, save_to_postgresql, save_to_google_sheets 

class TestLoad(unittest.TestCase):
    
    @patch('pandas.DataFrame.to_csv')
    def test_save_to_csv_success(self, mock_to_csv):
        df = pd.DataFrame({'Title': ['A'], 'Price': [100]})
        result = save_to_csv(df, 'dummy.csv')
        self.assertTrue(result)
        mock_to_csv.assert_called_once_with('dummy.csv', index=False)

    def test_save_to_csv_empty(self):
        df = pd.DataFrame()
        result = save_to_csv(df, 'dummy.csv')
        self.assertFalse(result)
    
    @patch('src.load.Credentials.from_service_account_file')
    @patch('src.load.gspread.authorize')
    def test_save_to_google_sheets_success(self, mock_authorize, mock_credentials):
        df = pd.DataFrame({'Title': ['Hat'], 'Price': [50000]})
        
        mock_client = mock_authorize.return_value
        mock_sheet = mock_client.open.return_value.sheet1
        
        result = save_to_google_sheets(df, 'dummy.json', 'Dummy_Sheet')
        
        self.assertTrue(result)
        mock_sheet.clear.assert_called_once()
        mock_sheet.update.assert_called_once()

    @patch('pandas.DataFrame.to_sql')
    @patch('src.load.create_engine')
    def test_save_to_postgresql_success(self, mock_create_engine, mock_to_sql):
        df = pd.DataFrame({'Title': ['Shirt'], 'Price': [100000]})
        
        mock_engine = mock_create_engine.return_value
        
        result = save_to_postgresql(df, 'postgresql://dummy:dummy@localhost/db', 'test_table')

        
        self.assertTrue(result)
        mock_to_sql.assert_called_once_with('test_table', mock_engine, if_exists='replace', index=False)


if __name__ == '__main__':
    unittest.main()