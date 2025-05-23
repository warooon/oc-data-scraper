import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY_V2")
    firecrawl_api_url = "https://api.firecrawl.dev/v1"
    
    target_urls = [
        # "https://www.elsegundo.org/",
        "https://311.sanantonio.gov/kb/docs/private/graffiti-and-waste-collection/grow-over-graffiti",
    ]

    # output_dir_raw = "crawler_output"
    # output_dir_llm = "llm_output"
    
    # compressed_raw = "crawler_output.tar.gz"
    # compressed_llm = "llm_output.tar.gz"
    
    output_dir_raw = "crawler_output_test"
    output_dir_llm = "llm_output_test"
    
    compressed_raw = "crawler_output_test.tar.gz"
    compressed_llm = "llm_output_test.tar.gz"

    aws_region = "us-east-2"
    bedrock_model_id = "arn:aws:bedrock:us-east-2:358607849468:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"