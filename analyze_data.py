#!/usr/bin/env python3
import sqlite3
import json
import datetime as dt
from collections import Counter, defaultdict
import matplotlib.pyplot as plt
import os

# Connect to the database
DB = sqlite3.connect("dme.db")
c = DB.cursor()

def analyze_posts_by_year():
    """Count posts per year and show trend"""
    c.execute("SELECT raw FROM items WHERE type='posts'")
    posts = c.fetchall()
    
    years = []
    for post in posts:
        data = json.loads(post[0])
        date = data.get('date', '')
        if date:
            year = date.split('-')[0]
            years.append(year)
    
    year_counts = Counter(years)
    
    print("\n=== Posts by Year ===")
    for year, count in sorted(year_counts.items()):
        print(f"{year}: {count} posts")
    
    # Create a directory for reports if it doesn't exist
    if not os.path.exists('reports'):
        os.makedirs('reports')
    
    # Plot the results
    plt.figure(figsize=(10, 6))
    x = list(sorted(year_counts.keys()))
    y = [year_counts[year] for year in x]
    plt.bar(x, y)
    plt.title('Posts by Year')
    plt.xlabel('Year')
    plt.ylabel('Number of Posts')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('reports/posts_by_year.png')
    print("\nChart saved as reports/posts_by_year.png")

def analyze_categories():
    """Analyze post categories"""
    c.execute("SELECT raw FROM items WHERE type='posts'")
    posts = c.fetchall()
    
    categories = []
    for post in posts:
        data = json.loads(post[0])
        cats = data.get('categories', [])
        categories.extend(cats)
    
    cat_counts = Counter(categories)
    
    print("\n=== Top Categories ===")
    print("ID\tCount")
    for cat_id, count in cat_counts.most_common(10):
        print(f"{cat_id}\t{count}")
    
    print("\nTo map category IDs to names:")
    print("curl -s \"https://dmeacademy.com/wp-json/wp/v2/categories?per_page=20\" | jq '.[] | {id, name}'")

def word_frequency():
    """Analyze word frequency in post titles"""
    c.execute("SELECT json_extract(raw, '$.title.rendered') FROM items WHERE type='posts'")
    titles = c.fetchall()
    
    words = []
    for title in titles:
        if title[0]:
            # Clean and split the title
            clean_title = title[0].lower().replace('&amp;', '').replace('&#8217;', "'")
            for char in ",.&#;:\"'!?()[]{}":
                clean_title = clean_title.replace(char, '')
            
            title_words = clean_title.split()
            words.extend([word for word in title_words if len(word) > 3])
    
    word_counts = Counter(words)
    
    print("\n=== Top Words in Titles ===")
    print("Word\tCount")
    for word, count in word_counts.most_common(20):
        print(f"{word}\t{count}")

def print_summary():
    """Print database summary"""
    c.execute("SELECT COUNT(*) FROM items")
    total = c.fetchone()[0]
    
    c.execute("SELECT type, COUNT(*) FROM items GROUP BY type")
    types = c.fetchall()
    
    c.execute("SELECT MIN(json_extract(raw, '$.date')), MAX(json_extract(raw, '$.date')) FROM items WHERE type='posts'")
    date_range = c.fetchone()
    
    print("\n=== Database Summary ===")
    print(f"Total items: {total}")
    for type_name, count in types:
        print(f"- {type_name}: {count} items")
    
    if date_range[0] and date_range[1]:
        print(f"Date range: {date_range[0]} to {date_range[1]}")

if __name__ == "__main__":
    print("DME Database Analysis")
    print("=" * 20)
    
    print_summary()
    analyze_posts_by_year()
    analyze_categories()
    word_frequency()
    
    print("\nAnalysis complete!")
    DB.close() 