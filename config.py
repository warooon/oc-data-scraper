import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY_V2")
    FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"
    
    # AWS Settings
    AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
    AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "genai-poc-s3-bucket")
    BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", 
        "arn:aws:bedrock:us-east-2:358607849468:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    
    # Target URLs - Add your city websites here
    TARGET_URLS = [
        "https://www.elsegundo.org/",
        "https://311.sanantonio.gov/",
        "https://www.sanantonio.gov/",
        # Add more city websites as needed
    ]
    
    # Output directories
    OUTPUT_RAW = "output/raw"
    OUTPUT_STRUCTURED = "output/structured"
    
    # Archive names
    ARCHIVE_RAW = "city_data_raw.tar.gz"
    ARCHIVE_STRUCTURED = "city_data_structured.tar.gz"
    
    # Scraping settings
    MAX_DEPTH = 5
    TIMEOUT = 30
    RETRY_ATTEMPTS = 3
    
    @classmethod
    def setup_directories(cls):
        """Create output directories"""
        Path(cls.OUTPUT_RAW).mkdir(parents=True, exist_ok=True)
        Path(cls.OUTPUT_STRUCTURED).mkdir(parents=True, exist_ok=True)