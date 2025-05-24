import asyncio
import requests
import time
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential
from config import Config

class FirecrawlScraper:
    """Simple Firecrawl scraper"""
    
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Config.FIRECRAWL_API_KEY}"
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def start_crawl(self, url: str) -> Optional[str]:
        """Start crawl job"""
        payload = {
            "url": url,
            "maxDepth": Config.MAX_DEPTH,
            "includePaths": [".*"],
            "excludePaths": [".*/admin.*", ".*/login.*", ".*/social.*"],
            "scrapeOptions": {
                "formats": ["html"],
                "timeout": 45000,
                "waitFor": 3000,
                "blockAds": True,
                "removeBase64Images": True
            }
        }
        
        response = requests.post(f"{Config.FIRECRAWL_API_URL}/crawl", 
                               headers=self.headers, json=payload)
        if response.status_code == 200:
            return response.json().get('id')
        else:
            print(f"❌ Firecrawl failed: {response.status_code}")
            return None
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=15, max=60))
    def get_status(self, job_id: str) -> Optional[Dict]:
        """Get job status"""
        response = requests.get(f"{Config.FIRECRAWL_API_URL}/crawl/{job_id}", 
                              headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return None
    
    def monitor_job(self, job_id: str) -> Optional[List[Dict]]:
        """Monitor job until completion"""
        print(f"⏳ Monitoring job: {job_id}")
        
        while True:
            status_data = self.get_status(job_id)
            if not status_data:
                return None
            
            status = status_data.get('status')
            print(f"📊 Status: {status}")
            
            if status == 'completed':
                return status_data.get('data', [])
            elif status in ['failed', 'stopped']:
                print(f"❌ Job failed: {status_data.get('error', 'Unknown')}")
                return None
            
            time.sleep(15)

class PlaywrightScraper:
    """Simple Playwright scraper for dynamic content"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.browser = None
        self.context = None
    
    async def setup(self):
        """Setup browser"""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent=self.ua.random,
                viewport={'width': 1920, 'height': 1080}
            )
    
    async def scrape_page(self, url: str) -> Optional[Dict]:
        """Scrape single page"""
        await self.setup()
        page = await self.context.new_page()
        
        try:
            print(f"🎭 Playwright scraping: {url}")
            response = await page.goto(url, wait_until='networkidle', timeout=Config.TIMEOUT * 1000)
            
            if not response or response.status >= 400:
                return None
            
            # Wait for dynamic content
            await asyncio.sleep(3)
            
            # Try clicking load more buttons
            await self._click_load_more(page)
            
            # Extract content
            html = await page.content()
            title = await page.title()
            
            # Extract calendar events
            events = await self._extract_events(page)
            
            # Extract tables
            tables = await self._extract_tables(page)
            
            # Extract forms
            forms = await self._extract_forms(page)
            
            return {
                'url': url,
                'html': html,
                'title': title,
                'events': events,
                'tables': tables,
                'forms': forms
            }
            
        except Exception as e:
            print(f"❌ Playwright error: {e}")
            return None
        finally:
            await page.close()
    
    async def _click_load_more(self, page):
        """Click load more buttons"""
        selectors = [
            'button:has-text("Load More")',
            'button:has-text("Show All")',
            '.load-more'
        ]
        
        for selector in selectors:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.click()
                    await asyncio.sleep(2)
            except:
                continue
    
    async def _extract_events(self, page):
        """Extract calendar events"""
        events = []
        selectors = ['.event', '.calendar-event', '.meeting', '.schedule-item']
        
        for selector in selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                for i in range(min(count, 20)):  # Limit to 20 events
                    text = await elements.nth(i).inner_text()
                    if text.strip():
                        events.append(text.strip())
            except:
                continue
        
        return events
    
    async def _extract_tables(self, page):
        """Extract table data"""
        tables = []
        try:
            table_elements = page.locator('table')
            count = await table_elements.count()
            
            for i in range(min(count, 10)):  # Limit to 10 tables
                table_text = await table_elements.nth(i).inner_text()
                if table_text.strip():
                    tables.append(table_text.strip())
        except:
            pass
        
        return tables
    
    async def _extract_forms(self, page):
        """Extract form information including signup forms"""
        forms = []
        try:
            form_elements = page.locator('form')
            count = await form_elements.count()
            
            for i in range(count):
                form = form_elements.nth(i)
                
                # Get form attributes
                action = await form.get_attribute('action') or ''
                method = await form.get_attribute('method') or 'GET'
                form_id = await form.get_attribute('id') or f'form_{i}'
                
                # Extract form fields
                fields = []
                inputs = form.locator('input, select, textarea')
                input_count = await inputs.count()
                
                for j in range(input_count):
                    input_elem = inputs.nth(j)
                    field_info = {
                        'type': await input_elem.get_attribute('type') or 'text',
                        'name': await input_elem.get_attribute('name') or '',
                        'id': await input_elem.get_attribute('id') or '',
                        'placeholder': await input_elem.get_attribute('placeholder') or '',
                        'required': await input_elem.get_attribute('required') is not None,
                        'label': ''
                    }
                    
                    # Try to find associated label
                    try:
                        label_text = await page.locator(f'label[for="{field_info["id"]}"]').inner_text()
                        field_info['label'] = label_text.strip()
                    except:
                        pass
                    
                    fields.append(field_info)
                
                # Determine form type
                form_text = await form.inner_text()
                form_type = self._classify_form_type(form_text, fields)
                
                form_data = {
                    'id': form_id,
                    'action': action,
                    'method': method.upper(),
                    'type': form_type,
                    'fields': fields,
                    'text': form_text[:500]  # First 500 chars
                }
                
                forms.append(form_data)
                
        except Exception as e:
            print(f"⚠️ Form extraction error: {e}")
        
        return forms
    
    def _classify_form_type(self, form_text: str, fields: list) -> str:
        """Classify the type of form based on content and fields"""
        text_lower = form_text.lower()
        field_names = [f.get('name', '').lower() for f in fields]
        field_types = [f.get('type', '').lower() for f in fields]
        
        # Check for signup/registration forms
        signup_keywords = ['sign up', 'register', 'create account', 'join', 'signup', 'registration']
        if any(keyword in text_lower for keyword in signup_keywords):
            return 'signup'
        
        # Check for login forms
        login_keywords = ['sign in', 'login', 'log in', 'signin']
        if any(keyword in text_lower for keyword in login_keywords):
            return 'login'
        
        # Check for contact forms
        contact_keywords = ['contact', 'message', 'inquiry', 'feedback']
        if any(keyword in text_lower for keyword in contact_keywords):
            return 'contact'
        
        # Check for application forms
        application_keywords = ['apply', 'application', 'permit', 'license', 'request']
        if any(keyword in text_lower for keyword in application_keywords):
            return 'application'
        
        # Check for newsletter/subscription
        if 'email' in field_names and ('subscribe' in text_lower or 'newsletter' in text_lower):
            return 'subscription'
        
        # Check for search forms
        if 'search' in field_names or 'q' in field_names:
            return 'search'
        
        return 'other'
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()

class CityScraper:
    """Main scraper orchestrator with fallback strategy"""
    
    def __init__(self):
        self.firecrawl = FirecrawlScraper()
        self.playwright = PlaywrightScraper()
        self.processed_items = []
        self.form_urls = []  # Collect URLs with forms for special handling
    
    async def scrape_all(self):
        """Main scraping method: Firecrawl -> Playwright fallback"""
        Config.setup_directories()
        
        for url in Config.TARGET_URLS:
            print(f"\n🚀 Processing: {url}")
            
            # Try Firecrawl first
            success = await self._try_firecrawl(url)
            
            # Fallback to Playwright if Firecrawl fails
            if not success:
                await self._try_playwright(url)
        
        # Handle any signup/form pages specifically
        await self._handle_form_pages()
        
        # Cleanup
        await self.playwright.cleanup()
        
        print(f"\n✅ Processed {len(self.processed_items)} items")
        return self.processed_items
    
    async def _try_firecrawl(self, url: str) -> bool:
        """Try Firecrawl scraping"""
        try:
            job_id = self.firecrawl.start_crawl(url)
            if not job_id:
                return False
            
            pages = self.firecrawl.monitor_job(job_id)
            if pages:
                # Check for form pages and add to special handling list
                for page in pages:
                    html = page.get('html', '')
                    if self._has_forms(html):
                        page_url = page.get('metadata', {}).get('url', url)
                        if page_url not in self.form_urls:
                            self.form_urls.append(page_url)
                
                self.processed_items.extend(pages)
                print(f"✅ Firecrawl success: {len(pages)} pages")
                return True
            
        except Exception as e:
            print(f"⚠️ Firecrawl failed: {e}")
        
        return False
    
    def _has_forms(self, html: str) -> bool:
        """Check if HTML contains forms"""
        import re
        form_indicators = [
            r'<form[^>]*>',
            r'sign\s*up',
            r'register',
            r'create\s*account',
            r'join\s*us',
            r'apply\s*online',
            r'request\s*service'
        ]
        
        html_lower = html.lower()
        return any(re.search(pattern, html_lower) for pattern in form_indicators)
    
    async def _handle_form_pages(self):
        """Handle pages with forms using Playwright for better extraction"""
        if not self.form_urls:
            return
            
        print(f"\n📝 Found {len(self.form_urls)} pages with forms, processing with Playwright...")
        
        for form_url in self.form_urls[:10]:  # Limit to 10 form pages
            try:
                result = await self.playwright.scrape_page(form_url)
                if result and result.get('forms'):
                    # Add to processed items if it has good form data
                    result['source'] = 'playwright_forms'
                    self.processed_items.append(result)
                    print(f"📝 Enhanced form data for: {form_url}")
            except Exception as e:
                print(f"⚠️ Form page processing failed for {form_url}: {e}")
    
    async def _try_playwright(self, url: str) -> bool:
        """Try Playwright scraping"""
        try:
            result = await self.playwright.scrape_page(url)
            if result:
                self.processed_items.append(result)
                print(f"✅ Playwright success: {url}")
                return True
                
        except Exception as e:
            print(f"❌ Playwright failed: {e}")
        
        return False
    
    def resume_job(self, job_id: str):
        """Resume Firecrawl job"""
        print(f"🔄 Resuming job: {job_id}")
        pages = self.firecrawl.monitor_job(job_id)
        if pages:
            self.processed_items.extend(pages)
        return pages