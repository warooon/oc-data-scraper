#!/usr/bin/env python3
"""
City Scraper - Comprehensive City Website Scraper
Fallback strategy: Firecrawl -> Playwright -> PDF/Form processing
"""

import asyncio
import time
from scrapers import CityScraper
from processors import ContentProcessor, DataSaver
from utils import extract_pdf_links, compress_directory, upload_to_s3, setup_logging, validate_config
from config import Config

async def main():
    """Main execution function"""
    
    setup_logging()
    start_time = time.time()
    
    print("🏛️ Starting City Scraper")
    print(f"📍 Target URLs: {len(Config.TARGET_URLS)}")
    
    # Validate configuration
    if not validate_config():
        print("❌ Configuration validation failed. Please check your settings.")
        return
    
    # Initialize components
    scraper = CityScraper()
    processor = ContentProcessor()
    saver = DataSaver()
    
    try:
        # Main scraping
        scraped_items = await scraper.scrape_all()
        
        if not scraped_items:
            print("❌ No data scraped")
            return
        
        print(f"\n📊 Processing {len(scraped_items)} items...")
        
        # Process and save each item
        pdf_links = []
        processed_count = 0
        
        for item in scraped_items:
            # Process main content
            processed_item = processor.process_page(item)
            if processed_item:
                saver.save_item(processed_item)
                processed_count += 1
                
                # Extract PDF links for later processing
                html = item.get('html', '')
                url = item.get('url', '')
                if html and url:
                    pdfs = extract_pdf_links(html, url)
                    pdf_links.extend(pdfs)
        
        # Process PDFs
        if pdf_links:
            unique_pdfs = list(set(pdf_links))  # Remove duplicates
            print(f"\n📄 Processing {len(unique_pdfs)} unique PDFs...")
            
            for i, pdf_url in enumerate(unique_pdfs[:15]):  # Limit to first 15 PDFs
                print(f"📄 Processing PDF {i+1}/{min(15, len(unique_pdfs))}: {pdf_url}")
                pdf_item = processor.download_and_process_pdf(pdf_url)
                if pdf_item:
                    saver.save_item(pdf_item)
                    processed_count += 1
        
        # Create archives
        print("\n📦 Creating archives...")
        compress_directory(Config.OUTPUT_RAW, Config.ARCHIVE_RAW)
        compress_directory(Config.OUTPUT_STRUCTURED, Config.ARCHIVE_STRUCTURED)
        
        # Upload to S3 (optional)
        if Config.AWS_S3_BUCKET:
            try:
                upload_to_s3(Config.ARCHIVE_RAW, f"city_scraper/{Config.ARCHIVE_RAW}")
                upload_to_s3(Config.ARCHIVE_STRUCTURED, f"city_scraper/{Config.ARCHIVE_STRUCTURED}")
            except:
                print("⚠️ S3 upload skipped (check AWS credentials)")
        
        # Final stats
        elapsed = (time.time() - start_time) / 60
        print(f"\n✅ City scraping completed in {elapsed:.2f} minutes")
        print(f"📊 Total items processed: {processed_count}")
        print(f"📁 Raw data: {Config.OUTPUT_RAW}")
        print(f"📁 Structured data: {Config.OUTPUT_STRUCTURED}")
        print(f"📦 Archives: {Config.ARCHIVE_RAW}, {Config.ARCHIVE_STRUCTURED}")
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await scraper.playwright.cleanup()

def resume_job(job_id: str):
    """Resume a Firecrawl job"""
    
    print(f"🔄 Resuming job: {job_id}")
    
    scraper = CityScraper()
    processor = ContentProcessor()
    saver = DataSaver()
    
    # Resume job and get results
    pages = scraper.resume_job(job_id)
    
    if pages:
        print(f"📊 Processing {len(pages)} resumed pages...")
        
        processed_count = 0
        for page in pages:
            processed_item = processor.process_page(page)
            if processed_item:
                saver.save_item(processed_item)
                processed_count += 1
        
        # Create archives
        compress_directory(Config.OUTPUT_RAW, Config.ARCHIVE_RAW)
        compress_directory(Config.OUTPUT_STRUCTURED, Config.ARCHIVE_STRUCTURED)
        
        print(f"✅ Resume completed - {processed_count} items processed")
    else:
        print("❌ No data found for job")

async def scrape_forms_only():
    """Scrape only forms and signup pages"""
    
    print("📝 Form-only scraping mode")
    
    # URLs that likely contain signup/registration forms
    form_urls = [
        "https://www.sanantonio.gov/Residents",
        "https://www.elsegundo.org/services",
        "https://311.sanantonio.gov/",
        # Add more specific form URLs as needed
    ]
    
    scraper = CityScraper()
    processor = ContentProcessor()
    saver = DataSaver()
    
    results = []
    try:
        for url in form_urls:
            print(f"📝 Scraping forms from: {url}")
            page_data = await scraper.playwright.scrape_page(url)
            
            if page_data and page_data.get('forms'):
                processed_item = processor.process_page(page_data)
                if processed_item:
                    saver.save_item(processed_item)
                    results.append(processed_item)
                    
                    # Print form summary
                    forms = page_data.get('forms', [])
                    for form in forms:
                        print(f"  📋 Found {form.get('type', 'unknown')} form: {form.get('id', 'unnamed')}")
                        print(f"      Action: {form.get('action', 'N/A')}")
                        print(f"      Fields: {len(form.get('fields', []))}")
    
    finally:
        await scraper.playwright.cleanup()
    
    return results

def show_help():
    """Show usage help"""
    print("""
🏛️ City Scraper - Usage Guide

Commands:
  python main.py                    # Normal scraping (all content)
  python main.py resume <job_id>    # Resume a Firecrawl job
  python main.py forms              # Scrape only forms and signup pages
  python main.py help               # Show this help

Configuration:
  1. Copy .env.example to .env
  2. Add your Firecrawl API key
  3. Configure AWS settings (optional)
  4. Edit config.py to add your city URLs

Output:
  - output/raw/          Raw scraped data
  - output/structured/   LLM-processed structured data
  - *.tar.gz            Compressed archives
  - scraper.log         Execution log

Examples:
  python main.py                           # Scrape all configured city websites
  python main.py resume abc123             # Resume job abc123
  python main.py forms                     # Focus on forms only
    """)

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "resume":
            if len(sys.argv) > 2:
                resume_job(sys.argv[2])
            else:
                print("❌ Please provide job ID: python main.py resume <job_id>")
        
        elif command == "forms":
            # Scrape only forms and signup pages
            results = asyncio.run(scrape_forms_only())
            print(f"✅ Found {len(results)} pages with forms")
        
        elif command == "help":
            show_help()
        
        else:
            print("❌ Unknown command. Use 'python main.py help' for usage guide.")
    
    else:
        # Normal execution
        asyncio.run(main())