import requests
from bs4 import BeautifulSoup
import pandas as pd

def scrape_fashion_data(base_url="https://fashion-studio.dicoding.dev", max_pages=50):
    """Extracts product data from Fashion Studio website."""
    data = []
    
    for page in range(1, max_pages + 1):
        if page == 1:
            url = f"{base_url}/"
        else:
            url = f"{base_url}/page{page}/"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            cards = soup.find_all('div', class_='collection-card')
            
            for card in cards:
                title = card.find('h3', class_='product-title').text.strip() if card.find('h3', class_='product-title') else None
                price_elem = card.find(class_='price')
                price = price_elem.text.strip() if price_elem else None
                details = card.find_all('p')
                rating = colors = size = gender = None
                
                for detail in details:
                    text = detail.text.strip()
                    if 'Rating:' in text: rating = text
                    elif 'Colors' in text: colors = text
                    elif 'Size:' in text: size = text
                    elif 'Gender:' in text: gender = text
                
                data.append({
                    'Title': title,
                    'Price': price,
                    'Rating': rating,
                    'Colors': colors,
                    'Size': size,
                    'Gender': gender
                })
                
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch data on page {page}: {e}")
            continue 
        
    return pd.DataFrame(data)