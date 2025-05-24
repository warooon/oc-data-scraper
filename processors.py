import json
import hashlib
import time
import requests
import fitz  # PyMuPDF
import boto3
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import io
import re
from pydantic import BaseModel
from config import Config

class ProcessedItem(BaseModel):
    url: str
    content_hash: str
    raw_text: str
    structured_data: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    timestamp: str

class ContentProcessor:
    """Simple content processor with LLM enhancement"""
    
    def __init__(self):
        self.bedrock = boto3.client("bedrock-runtime", region_name=Config.AWS_REGION)
        self.seen_hashes = set()
    
    def process_page(self, page_data: Dict) -> Optional[ProcessedItem]:
        """Process scraped page data"""
        url = page_data.get('url', '')
        html = page_data.get('html', '')
        
        if not html:
            return None
        
        # Create content hash
        content_hash = hashlib.md5(html.encode()).hexdigest()
        if content_hash in self.seen_hashes:
            return None
        self.seen_hashes.add(content_hash)
        
        # Clean content with LLM
        cleaned_text = self._clean_content(html)
        if not cleaned_text:
            return None
        
        # Extract structured data with LLM
        structured_data = self._extract_structured_data(cleaned_text, page_data)
        
        # Create metadata
        metadata = {
            "title": page_data.get('title', ''),
            "word_count": len(cleaned_text.split()),
            "has_events": bool(page_data.get('events', [])),
            "has_tables": bool(page_data.get('tables', [])),
            "has_forms": bool(page_data.get('forms', [])),
            "events_count": len(page_data.get('events', [])),
            "tables_count": len(page_data.get('tables', [])),
            "forms_count": len(page_data.get('forms', [])),
            "form_types": [f.get('type', 'unknown') for f in page_data.get('forms', [])]
        }
        
        return ProcessedItem(
            url=url,
            content_hash=content_hash,
            raw_text=cleaned_text,
            structured_data=structured_data,
            metadata=metadata,
            timestamp=str(int(time.time()))
        )
    
    def process_pdf(self, pdf_url: str, pdf_content: bytes) -> Optional[ProcessedItem]:
        """Process PDF content"""
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            
            if not text.strip():
                return None
            
            content_hash = hashlib.md5(text.encode()).hexdigest()
            if content_hash in self.seen_hashes:
                return None
            self.seen_hashes.add(content_hash)
            
            # Extract structured data
            structured_data = self._extract_pdf_data(text)
            
            return ProcessedItem(
                url=pdf_url,
                content_hash=content_hash,
                raw_text=text,
                structured_data=structured_data,
                metadata={"source": "pdf", "pages": len(doc)},
                timestamp=str(int(time.time()))
            )
            
        except Exception as e:
            print(f"❌ PDF processing failed: {e}")
            return None
    
    def _clean_content(self, html: str) -> str:
        """Clean HTML content using LLM"""
        prompt = f"""
        Clean this city/government website content. Keep only the main content, remove navigation, 
        footer, ads, and other noise. Preserve important information like:
        - Meeting schedules and events
        - Contact information
        - City services and forms
        - Official notices and announcements
        - Department information
        
        Return only the cleaned text.
        
        HTML (first 50,000 chars):
        {html[:50000]}
        """
        
        return self._call_claude(prompt)
    
    def _extract_structured_data(self, text: str, page_data: Dict) -> Dict[str, Any]:
        """Extract structured data using LLM"""
        
        # Add events, tables, and forms from Playwright
        events_text = "\n".join(page_data.get('events', []))
        tables_text = "\n".join(page_data.get('tables', []))
        
        # Add form information
        forms_info = []
        for form in page_data.get('forms', []):
            form_summary = f"Form Type: {form.get('type', 'unknown')}\n"
            form_summary += f"Action: {form.get('action', '')}\n"
            form_summary += f"Method: {form.get('method', 'GET')}\n"
            form_summary += "Fields:\n"
            for field in form.get('fields', []):
                form_summary += f"  - {field.get('label', field.get('name', 'unnamed'))}: {field.get('type', 'text')}"
                if field.get('required'):
                    form_summary += " (required)"
                form_summary += "\n"
            forms_info.append(form_summary)
        
        forms_text = "\n\n".join(forms_info)
        
        combined_text = f"{text}\n\nEvents:\n{events_text}\n\nTables:\n{tables_text}\n\nForms:\n{forms_text}"
        
        prompt = f"""
        Extract structured data from this city/government content. Return JSON with:
        {{
          "overview": "brief summary",
          "city_name": "name of city if mentioned",
          "departments": ["list of city departments"],
          "services": ["list of city services"],
          "contacts": [{{"name": "", "title": "", "phone": "", "email": "", "department": ""}}],
          "meetings": [{{"title": "", "date": "", "time": "", "location": "", "agenda": ""}}],
          "documents": [{{"title": "", "type": "", "url": "", "description": ""}}],
          "news": [{{"title": "", "date": "", "summary": ""}}],
          "forms": [{{
            "name": "",
            "type": "signup/login/contact/application/permit/other",
            "purpose": "",
            "url": "",
            "fields": ["list of field names"],
            "requirements": ["any requirements"]
          }}],
          "signup_info": {{
            "available": true/false,
            "description": "how to sign up for city services",
            "requirements": ["what's needed"],
            "benefits": ["what residents get"]
          }},
          "office_hours": {{"days": "", "hours": "", "location": "", "phone": ""}},
          "permits_licenses": [{{"type": "", "description": "", "fee": "", "requirements": []}}],
          "public_meetings": [{{"type": "", "frequency": "", "location": "", "contact": ""}}],
          "emergency_info": {{"phone": "", "website": "", "alerts": ""}},
          "other_info": "any other relevant city information"
        }}
        
        Content:
        {combined_text[:60000]}
        """
        
        try:
            result = self._call_claude(prompt)
            return json.loads(result) if result.strip().startswith('{') else {}
        except:
            return {}
    
    def _extract_pdf_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from PDF"""
        prompt = f"""
        Extract structured data from this city/government PDF document. Return JSON with:
        {{
          "document_type": "type of document (ordinance, report, agenda, etc.)",
          "title": "document title",
          "date": "document date if available",
          "department": "issuing department",
          "key_points": ["main points from document"],
          "dates": ["important dates mentioned"],
          "contacts": ["contact information"],
          "requirements": ["any requirements or procedures"],
          "fees": ["any fees or costs mentioned"],
          "deadlines": ["any deadlines"],
          "meeting_info": {{"date": "", "time": "", "location": ""}},
          "summary": "brief summary of document"
        }}
        
        PDF Text:
        {text[:40000]}
        """
        
        try:
            result = self._call_claude(prompt)
            return json.loads(result) if result.strip().startswith('{') else {}
        except:
            return {}
    
    def _call_claude(self, prompt: str) -> str:
        """Call Claude API via Bedrock"""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "max_tokens": 4000,
            "temperature": 0.2
        })
        
        try:
            response = self.bedrock.invoke_model(
                modelId=Config.BEDROCK_MODEL_ID,
                body=body
            )
            result = json.loads(response['body'].read())
            return result['content'][0]['text']
        except Exception as e:
            print(f"⚠️ LLM call failed: {e}")
            return ""
    
    def download_and_process_pdf(self, pdf_url: str) -> Optional[ProcessedItem]:
        """Download and process PDF from URL"""
        try:
            print(f"📄 Processing PDF: {pdf_url}")
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            return self.process_pdf(pdf_url, response.content)
            
        except Exception as e:
            print(f"❌ PDF download failed: {e}")
            return None

class DataSaver:
    """Simple data saver"""
    
    def __init__(self):
        Config.setup_directories()
    
    def save_item(self, item: ProcessedItem):
        """Save processed item"""
        
        # Save raw data
        raw_path = Path(Config.OUTPUT_RAW) / f"{item.content_hash}.json"
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(item.model_dump_json(indent=2))
        
        # Save structured data
        structured_path = Path(Config.OUTPUT_STRUCTURED) / f"{item.content_hash}.json"
        structured_data = {
            "url": item.url,
            "structured_data": item.structured_data,
            "metadata": item.metadata,
            "timestamp": item.timestamp
        }
        
        with open(structured_path, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved: {item.content_hash}")
    
    def save_batch(self, items: list):
        """Save multiple items"""
        for item in items:
            if isinstance(item, dict):
                # Convert dict to ProcessedItem if needed
                processor = ContentProcessor()
                processed_item = processor.process_page(item)
                if processed_item:
                    self.save_item(processed_item)
            else:
                self.save_item(item)