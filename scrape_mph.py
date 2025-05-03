import requests
import json
import re
from typing import List, Dict
import os

def scrape_mph_images(urls: List[Dict[str, str]], output_file: str = 'mph_products.json'):
    """Scrape multiple MPH URLs and combine the results"""
    print(f"Starting to scrape {len(urls)} URLs")
    
    # Headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    all_products = []
    seen_product_ids = set()  # To avoid duplicates
    
    for url_data in urls:
        url = url_data["url"]
        label = url_data["label"]
        print(f"\nProcessing URL: {url} ({label})")
        try:
            # Send GET request to the URL
            print("Sending GET request...")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            print("Successfully retrieved webpage")
            
            # Find the JSON data in the response
            print("Extracting JSON data...")
            json_match = re.search(r'Samita\.ProductLabels\.products\s*=\s*Samita\.ProductLabels\.products\.concat\((\[.*?\])\)', response.text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                # Clean up the JSON string
                json_str = json_str.replace('\n', '').replace('\t', '')
                products = json.loads(json_str)
                print(f"Found {len(products)} products")
                
                # Process each product
                for i, product in enumerate(products, 1):
                    product_id = product.get('id')
                    if product_id in seen_product_ids:
                        print(f"Skipping duplicate product {product_id}")
                        continue
                        
                    seen_product_ids.add(product_id)
                    print(f"\nProcessing product {i}/{len(products)}")
                    
                    # Extract relevant information
                    product_data = {
                        'id': product_id,
                        'title': product.get('title'),
                        'handle': product.get('handle'),
                        'price': product.get('price'),
                        'vendor': product.get('vendor'),
                        'featured_image': product.get('featured_image'),
                        'url': product.get('url'),
                        'tags': product.get('tags', []),
                        'images': product.get('images', []),
                        'variants': product.get('variants', []),
                        'source_url': url,  # Track which URL this product came from
                        'label': label  # Add the label
                    }
                    
                    print(f"Found product: {product_data['title']} - {product_data['price']}")
                    all_products.append(product_data)
            else:
                print("Could not find product data in the page")
            
        except requests.exceptions.RequestException as e:
            print(f"Error occurred while scraping {url}: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON data from {url}: {e}")
    
    # Save the combined data to a JSON file
    print(f"\nSaving {len(all_products)} unique products to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=4, ensure_ascii=False)
    
    print(f"Successfully scraped {len(all_products)} unique products and saved to {output_file}")

if __name__ == "__main__":
    # Example URLs to scrape
    urls = [
        {"url": "https://mphonline.com/collections/mph-best-of-2024", "label": "Best of 2024"},
        {"url": "https://mphonline.com/collections/mph-best-of-2023", "label": "Best of 2023"},
        {"url": "https://mphonline.com/collections/mph-best-of-2022", "label": "Best of 2022"},
        {"url": "https://mphonline.com/collections/mph-best-of-2021", "label": "Best of 2021"},
    ]
    
    
    scrape_mph_images(urls)