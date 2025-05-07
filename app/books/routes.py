import sqlite3
import json
from flask import render_template, request, current_app
from app.books import bp
import os

@bp.route('/')
def books():
    # Get page number from query parameter, default to 1
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    # Get sort parameters
    sort_by = request.args.get('sort', 'name')  # Default to name
    sort_order = request.args.get('order', 'asc')  # Default to ascending
    
    # Check if we're in default state
    is_default_state = sort_by == 'name' and sort_order == 'asc'
    
    valid_sorts = {
        'name': 'title',
        'price': 'CAST(price AS REAL)'  # Cast price to REAL for proper numeric sorting
    }
    sort_column = valid_sorts.get(sort_by, 'title')
    
    # Connect to database
    conn = sqlite3.connect(current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
    cursor = conn.cursor()
    
    # Get total count of books
    cursor.execute('SELECT COUNT(*) FROM products WHERE local_image_path IS NOT NULL')
    total_books = cursor.fetchone()[0]
    
    # Calculate total pages
    total_pages = (total_books + per_page - 1) // per_page
    
    # Get paginated products with sorting
    offset = (page - 1) * per_page
    cursor.execute(f'''
    SELECT p.id, p.title, p.price, p.vendor, p.local_image_path, p.url, p.labels
    FROM products p
    WHERE p.local_image_path IS NOT NULL
    ORDER BY {sort_column} {sort_order.upper()}
    LIMIT ? OFFSET ?
    ''', (per_page, offset))
    
    books = []
    for row in cursor.fetchall():
        product_id, title, price, vendor, main_image, url, labels_json = row
        
        # Convert path to URL
        main_image_url = f'/public/{os.path.basename(main_image)}' if main_image else None
        
        # Ensure URL is absolute
        if url and not url.startswith('http'):
            url = f'https://mphonline.com{url}'
        
        # Parse labels from JSON
        labels = json.loads(labels_json) if labels_json else []
        
        books.append({
            'id': product_id,
            'title': title,
            'price': int(price) if price is not None else 0,  # Store as integer cents
            'vendor': vendor,
            'main_image': main_image_url,
            'url': url,
            'labels': labels
        })
    
    conn.close()
    return render_template('books.html', 
                         books=books, 
                         current_page=page,
                         total_pages=total_pages,
                         current_sort=sort_by,
                         current_order=sort_order,
                         is_default_state=is_default_state) 