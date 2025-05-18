from dotenv import load_dotenv
load_dotenv()
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scraper import run_scraper_pipeline

if __name__ == "__main__":
    # Run on the actual DME Academy site
    site_url = "https://dmeacademy.com"
    print("Starting scraper pipeline test on DME Academy...")
    run_scraper_pipeline(site_url)
    print("Scraper pipeline test completed.") 