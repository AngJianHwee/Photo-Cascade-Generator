import json
import sqlite3
import os
import requests
from urllib.parse import urljoin
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# add a clean db
def clean_db():
    """Clean the database and images directory"""
    # Remove database if it exists
    if os.path.exists('mph_images.db'):
        os.remove('mph_images.db')
        print("Removed existing database")
    
    # Remove images directory if it exists
    images_dir = Path('images')
    if images_dir.exists():
        for file in images_dir.glob('*'):
            file.unlink()
        images_dir.rmdir()
        print("Cleaned images directory")

def setup_database():
    # Create database connection
    conn = sqlite3.connect('mph_images.db')
    cursor = conn.cursor()
    
    # Create table for products
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        title TEXT,
        handle TEXT,
        price INTEGER,  -- Store price as integer cents
        vendor TEXT,
        url TEXT,
        local_image_path TEXT,
        original_image_url TEXT,
        labels TEXT
    )
    ''')
    
    # Create table for product images
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        image_url TEXT,
        local_path TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')
    
    conn.commit()
    return conn, cursor

def download_image(args):
    """Download a single image"""
    url, save_path, product_id, image_type, conn = args
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Download the image
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Save the image
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Update database in a thread-safe way
        with sqlite3.connect('mph_images.db') as thread_conn:
            cursor = thread_conn.cursor()
            if image_type == 'featured':
                cursor.execute('''
                UPDATE products 
                SET local_image_path = ?, original_image_url = ?
                WHERE id = ?
                ''', (str(save_path), url, product_id))
            else:
                cursor.execute('''
                INSERT INTO product_images (product_id, image_url, local_path)
                VALUES (?, ?, ?)
                ''', (product_id, url, str(save_path)))
            thread_conn.commit()
        
        return True
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return False

def process_products(json_file, conn, cursor):
    # Create images directory
    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)
    
    # Read JSON file
    with open(json_file, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    # Prepare download tasks
    download_tasks = []
    
    for product in products:
        try:
            # Store labels as a JSON string
            labels = json.dumps([product['label']] if 'label' in product else [])
            
            # Convert price to integer cents
            price = product['price'] if product.get('price') else 0
            
            # Insert product into database
            cursor.execute('''
            INSERT INTO products (id, title, handle, price, vendor, url, labels)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                product['id'],
                product['title'],
                product['handle'],
                price,  # Store as integer cents
                product['vendor'],
                product['url'],
                labels
            ))
            
            # Process featured image
            if product.get('featured_image'):
                featured_image_url = urljoin('https://mphonline.com/cdn/shop/', product['featured_image'])
                local_path = images_dir / f"{product['id']}_featured.jpg"
                download_tasks.append((featured_image_url, local_path, product['id'], 'featured', conn))
            
            # Process additional images
            for img in product.get('images', []):
                if img.get('src'):
                    image_url = urljoin('https:', img['src'])
                    local_path = images_dir / f"{product['id']}_{img['id']}.jpg"
                    download_tasks.append((image_url, local_path, product['id'], 'additional', conn))
            
            print(f"Queued product: {product['title']}")
            
        except Exception as e:
            print(f"Error processing product {product.get('title')}: {e}")
            conn.rollback()
            continue
        
        conn.commit()
    
    # Download images in parallel
    print(f"\nDownloading {len(download_tasks)} images...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_image, task) for task in download_tasks]
        for future in tqdm(as_completed(futures), total=len(futures)):
            future.result()

def main():
    # Setup database
    conn, cursor = setup_database()
    
    try:
        # Process products from JSON file
        process_products('mph_products.json', conn, cursor)
        print("All products processed successfully!")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    main() 