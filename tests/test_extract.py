import unittest
from unittest.mock import patch, Mock
import pandas as pd
from src.extract import scrape_fashion_data

class TestExtract(unittest.TestCase):
    
    @patch('src.extract.requests.get')
    def test_scrape_fashion_data_success(self, mock_get):
        mock_html = """
        <html><body>
            <div class="collection-card">
                <h3 class="product-title">Cool Shirt</h3>
                <p class="price">$10.00</p>
                <p>Rating: 4.5 / 5</p>
                <p>3 Colors</p>
                <p>Size: M</p>
                <p>Gender: Men</p>
            </div>
        </body></html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode('utf-8')
        mock_get.return_value = mock_response
        result_df = scrape_fashion_data(max_pages=1)

        self.assertFalse(result_df.empty)
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df.iloc[0]['Title'], 'Cool Shirt')
        self.assertEqual(result_df.iloc[0]['Price'], '$10.00')

if __name__ == '__main__':
    unittest.main()