from municipal_scraper import MunicipalScraper
import time 

if __name__ == "__main__":
    start_time = time.time()
    
    scraper = MunicipalScraper()
    # scraper.scrape()
    
    scraper.resume_job("406383b8-1ee6-4fdf-a469-6a5914d2a63a")

    end_time = time.time()
    elapsed_minutes = (end_time - start_time) / 60
    
    print(f"Scraping complete. Total time: {elapsed_minutes:.2f} minutes.")
