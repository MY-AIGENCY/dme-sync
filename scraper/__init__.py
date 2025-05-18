import requests
from selectolax.parser import HTMLParser
import boto3
import time
import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

# 1.1 Read sitemap.xml and seed URL queue
def read_sitemap(sitemap_url: str) -> List[str]:
    """Fetch sitemap.xml and return a list of URLs to crawl."""
    resp = requests.get(sitemap_url, timeout=10)
    resp.raise_for_status()
    urls = []
    root = ET.fromstring(resp.content)
    for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        urls.append(url.text.strip())
    return urls

# 1.2 Respect robots.txt and throttle requests
class RobotsCache:
    def __init__(self):
        self.parsers = {}

    def get_parser(self, base_url: str) -> RobotFileParser:
        if base_url not in self.parsers:
            robots_url = urljoin(base_url, '/robots.txt')
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                pass  # If robots.txt can't be read, default to allow
            self.parsers[base_url] = rp
        return self.parsers[base_url]

robots_cache = RobotsCache()

def is_allowed_by_robots(url: str, user_agent: str = "*") -> bool:
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    rp = robots_cache.get_parser(base_url)
    return rp.can_fetch(user_agent, url)

def throttle_requests(last_request_time: float, min_interval: float = 0.5) -> float:
    now = time.time()
    elapsed = now - last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    return time.time()

# 1.3 Fetch with ETag/If-Modified-Since and 429 back-off
def fetch_url(url: str, etag: Optional[str] = None, last_modified: Optional[str] = None, max_retries: int = 3) -> Dict[str, Any]:
    headers = {}
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    for attempt in range(max_retries):
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', '2'))
            time.sleep(retry_after)
            continue
        if resp.status_code in (200, 304):
            return {
                'status_code': resp.status_code,
                'content': resp.text,
                'etag': resp.headers.get('ETag'),
                'last_modified': resp.headers.get('Last-Modified'),
                'url': url
            }
        resp.raise_for_status()
    raise Exception(f"Failed to fetch {url} after {max_retries} attempts")

# 1.4 Parse HTML with selectolax
def parse_html_blocks(html: str) -> Dict[str, Any]:
    tree = HTMLParser(html)
    blocks = {
        'h1': [n.text() for n in tree.css('h1')],
        'h2': [n.text() for n in tree.css('h2')],
        'h3': [n.text() for n in tree.css('h3')],
        'h4': [n.text() for n in tree.css('h4')],
        'h5': [n.text() for n in tree.css('h5')],
        'h6': [n.text() for n in tree.css('h6')],
        'p': [n.text() for n in tree.css('p')],
        'li': [n.text() for n in tree.css('li')],
        'table': [n.html for n in tree.css('table')],
        'meta': {n.attributes.get('property', n.attributes.get('name', '')): n.attributes.get('content', '') for n in tree.css('meta')},
        # schema.org extraction can be added here if needed
    }
    return blocks

# 1.6 Emit raw page JSON to S3/MinIO
def upload_to_s3(page_json: Dict[str, Any], key: str) -> None:
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )
    bucket = os.getenv('S3_BUCKET_NAME', 'raw-site-data')
    import json
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(page_json).encode('utf-8'))

# Example pipeline runner
def run_scraper_pipeline(sitemap_url: str):
    url_queue = read_sitemap(sitemap_url)
    last_request_time = 0.0
    for url in url_queue:
        if not is_allowed_by_robots(url):
            continue
        last_request_time = throttle_requests(last_request_time)
        try:
            result = fetch_url(url)
            if result['status_code'] == 304:
                continue  # Not modified
            html = result['content']
            etag = result.get('etag')
            last_modified = result.get('last_modified')
            blocks = parse_html_blocks(html)
            checksum = hashlib.sha256(html.encode('utf-8')).hexdigest()
            page_json = {
                'url': url,
                'html': html,
                'scraped_at': datetime.utcnow().isoformat(),
                'etag': etag,
                'checksum': checksum,
                'blocks': blocks
            }
            key = f"raw/{checksum}.json"
            upload_to_s3(page_json, key)
        except Exception as e:
            print(f"Error scraping {url}: {e}")
