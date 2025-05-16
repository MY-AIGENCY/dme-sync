#!/usr/bin/env python3
import sqlite3
import json
import datetime as dt
import hashlib
import os

def generate_id(data):
    """Generate a stable ID for an item"""
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

def convert_to_kb_format(item_type, item_id, raw_data):
    """Convert a raw database item to KB format"""
    data = json.loads(raw_data)
    
    # Extract title
    title = ""
    if isinstance(data.get("title"), dict) and "rendered" in data["title"]:
        title = data["title"]["rendered"]
    elif isinstance(data.get("title"), str):
        title = data["title"]
    
    # Extract content
    content = ""
    if isinstance(data.get("content"), dict) and "rendered" in data["content"]:
        content = data["content"]["rendered"]
    elif isinstance(data.get("content"), str):
        content = data["content"]
    
    # Extract URL
    url = data.get("link", "")
    
    # Extract date
    date = data.get("date", "")
    
    # Extract categories, sports, etc.
    categories = []
    if "categories" in data and data["categories"]:
        categories = data["categories"]
    
    sports = []
    if "sports" in data and data["sports"]:
        sports = data["sports"]
    
    # Create the KB item
    kb_item = {
        "id": generate_id(data),
        "original_id": item_id,
        "type": item_type,
        "title": title,
        "content": content,
        "url": url,
        "date": date,
        "categories": categories,
        "sports": sports,
        "raw": data  # Include the full raw data for completeness
    }
    
    return kb_item

def update_kb():
    print(f"[{dt.datetime.now()}] Starting KB update...")
    
    # Connect to the SQLite database
    db = sqlite3.connect("dme.db")
    cursor = db.cursor()
    
    # Get all items from the database
    cursor.execute("SELECT type, id, raw FROM items")
    items = cursor.fetchall()
    
    print(f"Found {len(items)} items in the database")
    
    # Load existing KB if it exists and has content
    kb = []
    try:
        if os.path.exists("master_kb.json") and os.path.getsize("master_kb.json") > 2:  # More than just '[]'
            with open("master_kb.json", "r") as f:
                kb = json.load(f)
            print(f"Loaded existing KB with {len(kb)} items")
    except Exception as e:
        print(f"Error loading existing KB: {e}")
        print("Starting with an empty KB")
    
    # Create a dictionary of existing KB items by original_id for quick lookup
    existing_items = {f"{item['type']}-{item['original_id']}": item for item in kb if "original_id" in item}
    
    # Process each database item
    new_kb = []
    new_count = 0
    updated_count = 0
    unchanged_count = 0
    
    for item_type, item_id, raw_data in items:
        key = f"{item_type}-{item_id}"
        kb_item = convert_to_kb_format(item_type, item_id, raw_data)
        
        if key not in existing_items:
            # New item
            new_kb.append(kb_item)
            new_count += 1
        else:
            # Existing item, check if it changed
            existing_item = existing_items[key]
            if existing_item.get("id") != kb_item["id"]:
                # Item changed, use new version but preserve any additional fields
                for field in existing_item:
                    if field not in kb_item and field != "id":
                        kb_item[field] = existing_item[field]
                new_kb.append(kb_item)
                updated_count += 1
            else:
                # Item unchanged, keep the existing version
                new_kb.append(existing_item)
                unchanged_count += 1
    
    # Save the updated KB
    with open("master_kb.json", "w") as f:
        json.dump(new_kb, f, indent=2)
    
    print(f"KB update complete:")
    print(f"- Total items: {len(new_kb)}")
    print(f"- New items: {new_count}")
    print(f"- Updated items: {updated_count}")
    print(f"- Unchanged items: {unchanged_count}")
    
    db.close()

if __name__ == "__main__":
    update_kb() 