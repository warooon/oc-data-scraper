import tarfile
import boto3
import re
import logging
from pathlib import Path
from typing import List, Dict
from config import Config
from urllib.parse import urljoin
from playwright.async_api import async_playwright



# def extract_pdf_links(html: str, base_url: str) -> List[str]:
#     """Extract PDF links from HTML"""
    
#     pdf_links = re.findall(r'href=[\'"]?([^\'" >]+\.pdf)', html, re.I)
    
#     # Convert relative URLs to absolute
#     absolute_links = []
#     for link in pdf_links:
#         if link.startswith('http'):
#             absolute_links.append(link)
#         else:
#             absolute_links.append(urljoin(base_url, link))
    
#     return list(set(absolute_links))  # Remove duplicates


async def extract_pdf_links(url: str) -> list:
    pdf_links = set()
    
    print("extracting pdf links")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)

        elements = await page.query_selector_all("a, iframe, embed, object")

        for el in elements:
            for attr in ['href', 'src', 'data']:
                val = await el.get_attribute(attr)
                if val and ('.pdf' in val.lower()):
                    full_url = page.url if val.startswith('http') else page.url + val
                    pdf_links.add(full_url)

            # Check for MIME type hints
            type_attr = await el.get_attribute('type')
            if type_attr and 'pdf' in type_attr.lower():
                src = await el.get_attribute('src') or await el.get_attribute('data')
                if src:
                    full_url = page.url if src.startswith('http') else page.url + src
                    pdf_links.add(full_url)

        await browser.close()
        
        print(pdf_links)

    return list(pdf_links)


def compress_directory(directory: str, archive_name: str):
    """Create compressed archive of directory"""
    print(f"📦 Creating archive: {archive_name}")
    
    with tarfile.open(archive_name, "w:gz") as tar:
        for file_path in Path(directory).glob("*.json"):
            tar.add(file_path, arcname=file_path.name)
    
    print(f"✅ Archive created: {archive_name}")

def upload_to_s3(file_path: str, s3_key: str) -> str:
    """Upload file to S3"""
    try:
        s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        
        with open(file_path, 'rb') as f:
            s3_client.upload_fileobj(f, Config.AWS_S3_BUCKET, s3_key)
        
        s3_url = f"https://{Config.AWS_S3_BUCKET}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"
        print(f"☁️ Uploaded to S3: {s3_url}")
        return s3_url
        
    except Exception as e:
        print(f"❌ S3 upload failed: {e}")
        return ""

def setup_logging():
    """Simple logging setup"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log'),
            logging.StreamHandler()
        ]
    )

def clean_text(text: str) -> str:
    """Basic text cleaning"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove non-printable characters
    text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)
    return text.strip()

def is_valid_url(url: str) -> bool:
    """Check if URL is valid"""
    return bool(re.match(r'^https?://', url))

def get_domain(url: str) -> str:
    """Extract domain from URL"""
    from urllib.parse import urlparse
    return urlparse(url).netloc

def format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def extract_city_info(text: str) -> Dict[str, str]:
    """Extract basic city information from text"""
    city_info = {}
    
    # Extract phone numbers
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phones = re.findall(phone_pattern, text)
    if phones:
        city_info['phones'] = phones[:3]  # First 3 phone numbers
    
    # Extract email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        city_info['emails'] = emails[:3]  # First 3 email addresses
    
    # Extract addresses (basic pattern)
    address_pattern = r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct)'
    addresses = re.findall(address_pattern, text, re.I)
    if addresses:
        city_info['addresses'] = addresses[:2]  # First 2 addresses
    
    return city_info

def validate_config():
    """Validate configuration settings"""
    issues = []
    
    if not Config.FIRECRAWL_API_KEY:
        issues.append("❌ FIRECRAWL_API_KEY is required")
    
    if not Config.TARGET_URLS:
        issues.append("❌ At least one TARGET_URL is required")
    
    if not Config.AWS_REGION:
        issues.append("⚠️ AWS_REGION not set, using default")
    
    if issues:
        print("\n🔧 Configuration Issues:")
        for issue in issues:
            print(f"   {issue}")
        print()
    
    return len(issues) == 0