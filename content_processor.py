import re
import json
import time
import hashlib
import urllib.parse
import fitz  
from pathlib import Path
from typing import Optional
from config import Config
from pydantic import BaseModel
import boto3

class ProcessedItem(BaseModel):
    url: str
    content_hash: str
    raw_text: str
    structured_json: Optional[dict] = {}
    metadata: dict
    timestamp: str

class ContentProcessor:
    def __init__(self):
        self.seen_hashes = set()
        self.bedrock = boto3.client("bedrock-runtime", region_name=Config.aws_region)

    def process_html(self, url: str, html: str) -> Optional[ProcessedItem]:
        content_hash = hashlib.md5(html.encode()).hexdigest()
        if content_hash in self.seen_hashes:
            return None
        self.seen_hashes.add(content_hash)

        cleaned_text = self.clean_html(html)
        if not cleaned_text:
            return None

        structured = self.extract_structured_json(cleaned_text)

        return ProcessedItem(
            url=self.normalize_url(url),
            content_hash=content_hash,
            raw_text=cleaned_text,
            structured_json=structured,
            metadata=self.get_metadata(html),
            timestamp=str(int(time.time()))
        )

    def process_pdf(self, url: str, pdf_bytes: bytes) -> Optional[ProcessedItem]:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            content_hash = hashlib.md5(text.encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes.add(content_hash)

            structured = self.extract_structured_json(text)

            return ProcessedItem(
                url=url,
                content_hash=content_hash,
                raw_text=text,
                structured_json=structured,
                metadata={"source": "pdf", "pages": len(doc)},
                timestamp=str(int(time.time()))
            )
        except Exception as e:
            print(f"[ERROR] PDF processing failed for {url}: {e}")
            return None

    def clean_html(self, html: str) -> str:
        prompt = f"""
        Clean this government website HTML content. Remove:
        - Navigation, footer, ads, social widgets, login/signup prompts

        Keep:
        - Main content, notices, meetings, documents, essential fields

        Return only cleaned text.

        HTML:
        {html[:100000]}
        """
        return self._invoke_claude(prompt)

    def extract_structured_json(self, text: str) -> dict:
        prompt = f"""
        Extract comprehensive structured data from this government content. Return JSON with:
        - overview: short excerpt (summary of the page)
        - meeting_schedules: list of {{title, date, time, location}}
        - departments: list of department names
        - contacts: list of {{name, title, phone, email}}
        - services: list of services provided
        - news: any latest news provided
        - documents: list of {{title, type, url}} if mentioned
        - other_relevant_info: any other relevant information
        
        Ensure collecting all the data comprehensively.
        Start the json directly with curly braces!
        

        Text:
        {text[:70000]}
        """
        try:
            result = self._invoke_claude(prompt)
            if not result.strip().startswith("{"):
                print("[WARN] LLM returned non-JSON content")
                return {}
            return json.loads(result)
        except Exception as e:
            print(f"[WARN] Failed to parse structured JSON: {e}")
            return {}


    def _invoke_claude(self, prompt: str) -> str:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "max_tokens": 3000,
            "temperature": 0.2
        })
        response = self.bedrock.invoke_model(
            modelId=Config.bedrock_model_id,
            body=body
        )
        raw = response['body'].read()
        parsed = json.loads(raw)
        return parsed['content'][0]['text']

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
        word_count = len(html.split())
        links = re.findall(r'href=[\'\"]?([^\'\" >]+)', html)
        num_links = len(links)
        num_pdf_links = sum(1 for link in links if link.lower().endswith('.pdf'))
        num_images = len(re.findall(r'<img\s', html, re.I))
        
        title_match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
        title = title_match.group(1).strip() if title_match else ""

        has_forms = bool(re.search(r'<form', html, re.I))

        return {
            "word_count": word_count,
            "links": num_links,
            "pdf_links": num_pdf_links,
            "images": num_images,
            "title": title,
            "has_forms": has_forms
        }