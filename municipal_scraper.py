import os
import time
import tarfile
import requests
import re
import json
from pathlib import Path
from config import Config
from urllib.parse import urljoin
from aws_helper import upload_to_s3
from firecrawl_client import FirecrawlAPIClient
from content_processor import ContentProcessor

class MunicipalScraper:
    def __init__(self):
        self.api = FirecrawlAPIClient()
        self.processor = ContentProcessor()
        self.seen_pdfs = set()
        Path(Config.output_dir_raw).mkdir(exist_ok=True)
        Path(Config.output_dir_llm).mkdir(exist_ok=True)

    def scrape(self):
        for url in Config.target_urls:
            try:
                print(f"Starting crawl: {url}")
                job_id = self.api.start_crawl(url)
                self.monitor_job(job_id)
            except Exception as e:
                print(f"[ERROR] Crawl failed for {url}: {e}")

        self.compress_outputs()

    def monitor_job(self, job_id: str):
        while True:
            try:
                status = self.api.get_crawl_status(job_id)
                print(f"Job {job_id} status: {status['status']}")

                if status['status'] == 'completed':
                    self.process_pages(status.get('data', []))
                    break
                if status['status'] in ['failed', 'stopped']:
                    print(f"[ERROR] Job failed: {status.get('error', 'Unknown error')}")
                    break
                time.sleep(15)
            except Exception as e:
                print(f"[ERROR] Status check failed: {e}")
                break

    def process_pages(self, pages: list):
        
        existing_hashes = {f.stem for f in Path(Config.output_dir_raw).glob("*.json")}
        
        for page in pages:
            url = page.get("metadata", {}).get("url", "")
            page_type = page.get("type", "html")
            print(f"[CRAWLED] {url} ({page_type})")

            html = page.get("html", "")
            if html:
                item = self.processor.process_html(url, html)
                if item and item.content_hash not in existing_hashes:
                    self.save_item(item)

                    for link in self.extract_links(html):
                        if link.lower().endswith(".pdf"):
                            self.download_and_process_pdf(link, base_url=url)
                else:
                    print(f"[SKIPPED] Already processed: {url}")


    def extract_links(self, html: str) -> list:
        return re.findall(r'href=[\'"]?([^\'" >]+)', html)

    from urllib.parse import urljoin

    def download_and_process_pdf(self, link: str, base_url: str):
        if not link.lower().startswith("http"):
            link = urljoin(base_url, link)

        if link in self.seen_pdfs:
            return
        self.seen_pdfs.add(link)

        try:
            print(f"[PDF] Downloading: {link}")
            response = requests.get(link, timeout=20)
            response.raise_for_status()
            
            item = self.processor.process_pdf(link, response.content)
            if item:
                self.save_item(item)
                print(f"[PDF] Processed and saved: {link}")
            else:
                print(f"[WARN] No data extracted from PDF: {link}")
        except Exception as e:
            print(f"[WARN] Failed to download/process PDF: {link} - {e}")


    def save_item(self, item):
        raw_path = Path(Config.output_dir_raw) / f"{item.content_hash}.json"
        llm_path = Path(Config.output_dir_llm) / f"{item.content_hash}.json"

        with open(raw_path, "w") as f:
            f.write(json.dumps({
                "url": item.url,
                "text": item.raw_text,
                "metadata": item.metadata,
                "timestamp": item.timestamp
            }, indent=2))

        with open(llm_path, "w") as f:
            f.write(json.dumps({
                "url": item.url,
                "structured_data": item.structured_json,
                "timestamp": item.timestamp
            }, indent=2))

    
    def compress_outputs(self):
        self._compress_folder(Config.output_dir_raw, Config.compressed_raw)
        self._compress_folder(Config.output_dir_llm, Config.compressed_llm)

        try:
            url_raw = upload_to_s3(Config.compressed_raw, Config.compressed_raw)
            url_llm = upload_to_s3(Config.compressed_llm, Config.compressed_llm)
            print(f"✅ Uploaded raw archive: {url_raw}")
            print(f"✅ Uploaded LLM archive: {url_llm}")
        except Exception as e:
            print(f"[ERROR] Upload failed: {e}")


    def _compress_folder(self, folder: str, archive_name: str):
        with tarfile.open(archive_name, "w:gz") as tar:
            for file in Path(folder).glob("*.json"):
                tar.add(file, arcname=file.name)
                
    
    # incase any error - can resume by inputting job_id rather than going through the scraping again
                
    def resume_job(self, job_id: str):
        print(f"Resuming job: {job_id}")
        while True:
            try:
                status = self.api.get_crawl_status(job_id)
                print(f"Job {job_id} status: {status['status']}")

                if status['status'] == 'completed':
                    self.process_pages(status.get('data', []))
                    print(f"Job {job_id} completed and processed.")
                    break
                if status['status'] in ['failed', 'stopped']:
                    print(f"[ERROR] Job {job_id} failed or stopped: {status.get('error', 'Unknown error')}")
                    break
                time.sleep(15)
            except Exception as e:
                print(f"[ERROR] Status check failed for job {job_id}: {e}")
                break