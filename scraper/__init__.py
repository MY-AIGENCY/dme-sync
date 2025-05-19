from dotenv import load_dotenv
load_dotenv()
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
from bs4 import BeautifulSoup
import json

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
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(page_json).encode('utf-8'))

def fetch_wordpress_content(base_url: str) -> List[Dict[str, Any]]:
    """Fetch all posts and pages from the WordPress REST API."""
    all_content = []
    endpoints = ["/wp-json/wp/v2/posts", "/wp-json/wp/v2/pages"]
    headers = {"User-Agent": "DME-KB-Sync"}
    for endpoint in endpoints:
        page = 1
        while True:
            url = f"{base_url}{endpoint}?per_page=100&page={page}"
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                for rec in data:
                    all_content.append({
                        'type': endpoint.split('/')[-1],
                        'id': rec.get('id'),
                        'raw': rec,
                        'url': rec.get('link'),
                        'scraped_at': datetime.utcnow().isoformat(),
                        'checksum': hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
                    })
                page += 1
            except Exception as e:
                print(f"[WARN] Error fetching {url}: {e}")
                break
    print(f"[INFO] Fetched {len(all_content)} items from WordPress REST API.")
    return all_content

# Update discover_urls to return ('wordpress', content) if API is available
def discover_urls(site_url: str):
    """
    Multi-strategy content discovery:
    1. Try sitemap.xml for URLs
    2. If fails, check for WordPress REST API and fetch full content
    3. Fallback: crawl for URLs
    Returns: ('wordpress', content) or ('urls', url_list)
    """
    parsed = urlparse(site_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_url = urljoin(base_url, '/sitemap.xml')
    print(f"[INFO] Attempting to fetch sitemap: {sitemap_url}")
    try:
        resp = requests.get(sitemap_url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        urls = [url.text.strip() for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        print(f"[INFO] Found {len(urls)} URLs in sitemap.xml")
        return ('urls', urls)
    except Exception as e:
        print(f"[WARN] Could not fetch sitemap.xml: {e}")
    # Try WordPress REST API for full content
    print(f"[INFO] Checking for WordPress REST API at {base_url}/wp-json/wp/v2/posts")
    try:
        test_url = urljoin(base_url, '/wp-json/wp/v2/posts?per_page=1')
        resp = requests.get(test_url, headers={"User-Agent": "DME-KB-Sync"}, timeout=10)
        if resp.status_code == 200 and resp.headers.get('Content-Type', '').startswith('application/json'):
            content = fetch_wordpress_content(base_url)
            if content:
                return ('wordpress', content)
    except Exception as e:
        print(f"[WARN] Could not use WordPress REST API: {e}")
    # Fallback: respectful crawl for URLs
    print(f"[INFO] Falling back to respectful crawl from homepage: {base_url}")
    to_visit = [base_url]
    seen = set()
    discovered = []
    max_pages = 50
    while to_visit and len(discovered) < max_pages:
        url = to_visit.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not is_allowed_by_robots(url):
            print(f"[INFO] Skipping disallowed by robots.txt: {url}")
            continue
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            discovered.append(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all('a', href=True):
                link = urljoin(base_url, a['href'])
                if link.startswith(base_url) and link not in seen and link not in to_visit:
                    to_visit.append(link)
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] Error crawling {url}: {e}")
    print(f"[INFO] Discovered {len(discovered)} URLs via crawl.")
    return ('urls', discovered)

def append_run_log(method: str, count: int, manifest_key: str):
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )
    bucket = os.getenv('S3_BUCKET_NAME', 'raw-site-data')
    import json
    log_key = 'run_history.jsonl'
    record = {
        'timestamp': datetime.utcnow().isoformat(),
        'method': method,
        'count': count,
        'manifest_key': manifest_key
    }
    # Download existing log if present
    try:
        resp = s3.get_object(Bucket=bucket, Key=log_key)
        lines = resp['Body'].read().decode().splitlines()
    except s3.exceptions.NoSuchKey:
        lines = []
    lines.append(json.dumps(record))
    s3.put_object(Bucket=bucket, Key=log_key, Body='\n'.join(lines).encode('utf-8'))
    print(f"[INFO] Appended run log to S3: {log_key}")

# Simple change detection between latest two manifests
def compare_manifests(bucket: str, manifest_keys: list):
    if len(manifest_keys) < 2:
        print("[INFO] Not enough manifests for change detection.")
        return
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )
    import json
    m1 = json.loads(s3.get_object(Bucket=bucket, Key=manifest_keys[-2])['Body'].read())
    m2 = json.loads(s3.get_object(Bucket=bucket, Key=manifest_keys[-1])['Body'].read())
    set1 = set(m1.get('items', m1.get('urls', [])))
    set2 = set(m2.get('items', m2.get('urls', [])))
    new = set2 - set1
    removed = set1 - set2
    print(f"[CHANGE DETECTION] New items: {len(new)}, Removed items: {len(removed)}")

# Update pipeline runner to log and compare manifests
def run_scraper_pipeline(site_url: str):
    mode, data = discover_urls(site_url)
    last_request_time = 0.0
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )
    bucket = os.getenv('S3_BUCKET_NAME', 'raw-site-data')
    import json
    if mode == 'wordpress':
        manifest = {'type': 'wordpress', 'count': len(data), 'items': [i['url'] for i in data]}
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        manifest_key = f"manifests/wordpress_manifest_{timestamp}.json"
        s3.put_object(Bucket=bucket, Key=manifest_key, Body=json.dumps(manifest, indent=2).encode('utf-8'))
        print(f"[INFO] Uploaded manifest to S3: {manifest_key}")
        append_run_log('wordpress', len(data), manifest_key)
        # List all manifest keys for change detection
        resp = s3.list_objects_v2(Bucket=bucket, Prefix='manifests/wordpress_manifest_')
        manifest_keys = sorted([obj['Key'] for obj in resp.get('Contents', [])])
        compare_manifests(bucket, manifest_keys)
        for item in data:
            key = f"raw/wp_{item['type']}_{item['id']}_{item['checksum']}.json"
            upload_to_s3(item, key)
    else:
        manifest = {'type': 'urls', 'count': len(data), 'urls': data}
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        manifest_key = f"manifests/urls_manifest_{timestamp}.json"
        s3.put_object(Bucket=bucket, Key=manifest_key, Body=json.dumps(manifest, indent=2).encode('utf-8'))
        print(f"[INFO] Uploaded manifest to S3: {manifest_key}")
        append_run_log('urls', len(data), manifest_key)
        resp = s3.list_objects_v2(Bucket=bucket, Prefix='manifests/urls_manifest_')
        manifest_keys = sorted([obj['Key'] for obj in resp.get('Contents', [])])
        compare_manifests(bucket, manifest_keys)
        for url in data:
            last_request_time = throttle_requests(last_request_time)
            try:
                result = fetch_url(url)
                if result['status_code'] == 304:
                    continue
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
