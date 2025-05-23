import requests
import time
from config import Config


class FirecrawlAPIClient:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.firecrawl_api_key}"
        }

    def start_crawl(self, url: str) -> str:
        payload = {
            "url": url,
            "maxDepth": 5,
            "includePaths": [".*"],
            "excludePaths": [".*/social-media.*"],
            "scrapeOptions": {
                "formats": ["html"],
                "proxy": "basic",
                "removeBase64Images": True,
                "blockAds": True
            }
        }
        response = requests.post(
            f"{Config.firecrawl_api_url}/crawl",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()['id']

    
    def get_crawl_status(self, job_id: str, retries: int = 5, delay: int = 15) -> dict:
        for attempt in range(retries):
            try:
                response = requests.get(
                    f"{Config.firecrawl_api_url}/crawl/{job_id}",
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                if response.status_code in [502, 503, 504]:
                    print(f"[WARN] Transient error (attempt {attempt+1}/{retries}): {e}")
                    time.sleep(delay)
                else:
                    raise

            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}")
                time.sleep(delay)

        raise RuntimeError(f"Failed to get crawl status after {retries} attempts.")