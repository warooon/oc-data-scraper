'''
    [CHANGELOG]
        - Updated Payload in FirecrawlAPIClient.start_crawl() to align as per the Documentation
        - Changed fircrawl crawling api v2 to v1
        - Changed url from 311.sanantonio.gov (invalid) to www.sanantonio.gov
        - Changed bedrock_model_id to include the whole ARN due to .invoke requiring inference profile
        - Changed AWS region from us-east-1 to us-east-2 (my account region)
        - Changed FirecrawlAPIClient.start_crawl() return call to return 'id' instead of 'jobid' (incorrect)
        - Changed FirecrawlAPIClient.get_crawl_status() get request URL from /crawl/status/{job_id} (incorrect) to just /crawl/{job_id}
        - Added Debug statements in
            - ContentProcessor.ContentProcessor()
            - MunicipalScraper.process_pages()
            - MunicipalScraper.is_valid_page()
        - Changed MunicipalScraper completed status statement to align with the data as a list shared by Firecrawl API
        - Changed content check for 'sign up' to checking the same in tags (as pages were being rejected) (commented out for now)
        - Changed MunicipalScraper.compress_results() to upload the tar.gz file to S3
'''

import os
import re
import json
import time
import requests
import hashlib
import tarfile
import urllib.parse
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel
import boto3
from awsHelper import upload_to_s3


load_dotenv()

class Config:
    firecrawl_api_key =  os.getenv("FIRECRAWL_API_KEY_V2")
    firecrawl_api_url = "https://api.firecrawl.dev/v1" 
    target_urls = ["https://www.elsegundo.org", "https://www.sanantonio.gov"] 
    # target_urls = ["https://www.google.com"]

    output_dir = "scraped_data"
    
    compressed_file = "output.tar.gz"
    max_depth = 2
    # bedrock_model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_model_id = "arn:aws:bedrock:us-east-2:358607849468:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0" 
    aws_region = "us-east-2" 

class ProcessedItem(BaseModel):
    text: str
    url: str
    content_hash: str
    entities: list[str] = []
    metadata: dict = {}
    timestamp: str

class FirecrawlAPIClient:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.firecrawl_api_key}"
        }

    def start_crawl(self, url: str) -> str:
        """Start crawl job with advanced options"""
        
        payload = {
            "url": url,
            "maxDepth": Config.max_depth,
            "includePaths": [".*"],
            "excludePaths": [".*/login.*", ".*/social-media.*", ".*/signup.*"],
            "scrapeOptions": {
                "formats": ["html"],
                # "onlyMainContent": True,
                # "timeout": 30000,
                "proxy": "basic",
                "removeBase64Images": True,
                "blockAds": True
            }
        }

        try:
            response = requests.post(
                f"{Config.firecrawl_api_url}/crawl",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()['id'] # changed
        except Exception as e:
            raise RuntimeError(f"Failed to start crawl: {str(e)}")

    def get_crawl_status(self, job_id: str) -> dict:
        """Check crawl job status"""
        try:
            response = requests.get(
                f"{Config.firecrawl_api_url}/crawl/{job_id}",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to check status: {str(e)}")

class ContentProcessor:
    def __init__(self):
        self.seen_hashes = set()
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=Config.aws_region
        )

    def process_content(self, url: str, html: str) -> Optional[ProcessedItem]:
        
        print(f"[DEBUG] Processing URL: {url}, HTML length: {len(html)}")

        try:
            url = self.normalize_url(url)
            content_hash = hashlib.md5(html.encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes.add(content_hash)

            cleaned_text = self.clean_content(html)
            if not cleaned_text:
                return None

            entities = self.extract_entities(cleaned_text)
           
            return ProcessedItem(
                text=cleaned_text,
                url=url,
                content_hash=content_hash,
                entities=entities,
                metadata=self.get_metadata(html),
                timestamp=str(int(time.time()))
            )
        except Exception as e:
            print(f"Content processing failed: {str(e)}")
            return None

    def clean_content(self, html: str) -> str:
        """Use Bedrock to clean HTML content"""
        prompt = f"""
        Clean this government website content by removing:
        - Navigation menus
        - Footer content
        - Ads/promotions
        - Social media widgets
        - Login/signup prompts
       
        Preserve:
        - Main article text
        - Government notices
        - Meeting schedules
        - Official documents
       
        Return only the cleaned text.
       
        HTML Content:
        {html[:15000]}
        """
       
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }],
            "max_tokens": 3000,
            "temperature": 0.2
        })
        
        try:
            response = self.bedrock.invoke_model(
                modelId=Config.bedrock_model_id,
                body=body
            )
            
            raw = response['body'].read()
            parsed = json.loads(raw)
            return parsed['content'][0]['text']
        except Exception as e:
            print(f"Content cleaning failed: {str(e)}")
            return ""

    def extract_entities(self, text: str) -> list[str]:

        prompt = f"""
        Extract government-related entities from this text.
        Return a JSON array of strings.
       
        Text:
        {text[:10000]}
        """
       
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }],
            "max_tokens": 1000,
            "temperature": 0.1
        })
       
        try:
            response = self.bedrock.invoke_model(
                modelId=Config.bedrock_model_id,
                body=body
            )
            return json.loads(json.loads(response['body'].read())['content'][0]['text'])
        except Exception:
            return []

    @staticmethod
    def normalize_url(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((
            "https" if parsed.scheme in ["http", "https"] else parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),
            parsed.params,
            parsed.query,
            ""
        ))

    @staticmethod
    def get_metadata(html: str) -> dict:
        return {
            "word_count": len(html.split()),
            "links": len(re.findall(r'href=[\'"]?([^\'" >]+)', html)),
            "has_forms": bool(re.search(r'<form', html, re.I))
        }

class MunicipalScraper:
    def __init__(self):
        self.api = FirecrawlAPIClient()
        self.processor = ContentProcessor()

    def scrape(self):
        Path(Config.output_dir).mkdir(exist_ok=True)
       
        for url in Config.target_urls:
            try:
                print(f"Starting crawl: {url}")
                job_id = self.api.start_crawl(url)
                self.monitor_job(job_id)
            except Exception as e:
                print(f"Crawl failed for {url}: {str(e)}")

        self.compress_results()

    def monitor_job(self, job_id: str):
        """Track crawl job progress"""
        while True:
            try:
                status = self.api.get_crawl_status(job_id)
                print(f"Job {job_id} status: {status['status']}")
               
                if status['status'] == 'completed':
                    self.process_pages(status.get('data', []))
                    break
                if status['status'] in ['failed', 'stopped']:
                    print(f"Job failed: {status.get('error', 'Unknown error')}")
                    break
                time.sleep(15)
            except Exception as e:
                print(f"Status check failed: {str(e)}")
                break

    def process_pages(self, pages: list):
        """Process scraped pages"""
        print(f"[DEBUG] process_pages() called with {len(pages)} pages")
        for idx, page in enumerate(pages):
            metadata = page.get('metadata', {})
            url = metadata.get('url', 'N/A')
            html_length = len(page.get('html', '')) if page.get('html') else 0
            
            if self.is_valid_page(page):
                item = self.processor.process_content(url, page.get('html', ''))
                if item:
                    self.save_item(item)

    def is_valid_page(self, page: dict) -> bool:
        """Validate page content"""
        content = page.get('html', '').lower()
        status = page.get('statusCode', 200)
        
        if status >= 400:
            print(f"[DEBUG] Rejected page due to status code: {status}")
            return False
        if 'page not found' in content:
            print(f"[DEBUG] Rejected page due to 'page not found'")
            return False
        # if 'sign up' in content:
        #     print(f"[DEBUG] Rejected page due to 'sign up'")
        # if re.search(r'<.*sign\s*up.*>', content):
        #     print(f"[DEBUG] Rejected page due to 'sign up' in tag")
        #     return False
        if 'login' in content:
            print(f"[DEBUG] Rejected page due to 'login'")
            return False

        return True


    def save_item(self, item: ProcessedItem):
        filename = f"{item.content_hash}.json"
        filepath = Path(Config.output_dir) / filename
        with open(filepath, 'w') as f:
            f.write(item.model_dump_json(indent=2))

    def compress_results(self):
        with tarfile.open(Config.compressed_file, "w:gz") as tar:
            for file in Path(Config.output_dir).glob("*.json"):
                tar.add(file, arcname=file.name)

        try:
            s3_url = upload_to_s3(Config.compressed_file, Config.compressed_file)
            print(f"Archive uploaded to: {s3_url}")
        except Exception as e:
            print(f"Failed to upload to S3: {str(e)}")


if __name__ == "__main__":
    scraper = MunicipalScraper()
    scraper.scrape()
    print(f"Scraping complete. Output saved to {Config.compressed_file}")