from dotenv import load_dotenv
load_dotenv()
import requests

base_url = 'https://dmeacademy.com'
endpoints = ['/wp-json/wp/v2/posts', '/wp-json/wp/v2/pages']
headers = {'User-Agent': 'DME-KB-Sync'}

for endpoint in endpoints:
    url = f'{base_url}{endpoint}?per_page=1'
    resp = requests.get(url, headers=headers, timeout=10)
    print(f'Endpoint: {endpoint}')
    print('X-WP-Total:', resp.headers.get('X-WP-Total'))
    print('X-WP-TotalPages:', resp.headers.get('X-WP-TotalPages'))
    print('Status:', resp.status_code)
    print('-'*40) 