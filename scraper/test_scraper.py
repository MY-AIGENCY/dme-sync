from dotenv import load_dotenv
load_dotenv()
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scraper import run_scraper_pipeline

if __name__ == "__main__":
    # Use a public sitemap for testing
    sitemap_url = "https://www.gov.uk/sitemap.xml"
    print("Starting scraper pipeline test...")
    run_scraper_pipeline(sitemap_url)
    print("Scraper pipeline test completed.") 