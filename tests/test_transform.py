import unittest
import pandas as pd
from src.transform import clean_data

class TestTransform(unittest.TestCase):
    
    def test_clean_data_success(self):
        raw_data = {
            'Title': ['Shirt A', 'Unknown Product', 'Pants B'],
            'Price': ['$10.00', '$20.00', 'Price Unavailable'],
            'Rating': ['Rating: 4.5 / 5', 'Invalid Rating', 'Rating: 5.0 / 5'],
            'Colors': ['3 Colors', '2 Colors', '1 Colors'],
            'Size': ['Size: M', 'Size: L', 'Size: S'],
            'Gender': ['Gender: Men', 'Gender: Women', 'Gender: Unisex']
        }
        df_raw = pd.DataFrame(raw_data)
        df_clean = clean_data(df_raw)
        
        self.assertEqual(len(df_clean), 1)
        self.assertEqual(df_clean.iloc[0]['Title'], 'Shirt A')
        
        # Validate price (10.00 * 16000 = 160000)
        self.assertEqual(df_clean.iloc[0]['Price'], 160000.0)
        
        self.assertEqual(df_clean.iloc[0]['Size'], 'M')

if __name__ == '__main__':
    unittest.main()